from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, EsrganImageUpscaleModelActionConfig
from mindor.core.logger import logging
from ....base import ComponentActionContext
from ..common import ImageUpscaleTaskService, ImageUpscaleTaskAction
from PIL import Image as PILImage
import asyncio

if TYPE_CHECKING:
    from basicsr.archs.rrdbnet_arch import RRDBNet
    from torch import Tensor
    import torch

class EsrganImageUpscaleTaskAction(ImageUpscaleTaskAction):
    config: EsrganImageUpscaleModelActionConfig

    def __init__(
        self,
        config: EsrganImageUpscaleModelActionConfig,
        model: RRDBNet,
        device: Optional[torch.device]
    ):
        super().__init__(config, device)

        self.model: RRDBNet = model

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        tile_size      = await context.render_variable(self.config.params.tile_size)
        tile_pad_size  = await context.render_variable(self.config.params.tile_pad_size)
        pre_pad_size   = await context.render_variable(self.config.params.pre_pad_size)
        half_precision = await context.render_variable(self.config.params.half_precision)

        params.update({
            "tile_size":      tile_size,
            "tile_pad_size":  tile_pad_size,
            "pre_pad_size":   pre_pad_size,
            "half_precision": half_precision,
            "scale":          self.config.scale,
        })

        return params

    async def _upscale(self, images: List[PILImage.Image], params: Dict[str, Any], loop: asyncio.AbstractEventLoop) -> List[PILImage.Image]:
        return await loop.run_in_executor(None, self._upscale_batch, images, params)

    def _upscale_batch(self, images: List[PILImage.Image], params: Dict[str, Any]) -> List[PILImage.Image]:
        import torch
        import numpy as np

        results: List[PILImage.Image] = []

        for image in images:
            image_pixels = np.array(image).astype(np.float32) / 255.0

            if len(image_pixels.shape) == 3:
                tensor_image = torch.from_numpy(image_pixels).permute(2, 0, 1).unsqueeze(0)
            else:
                tensor_image = torch.from_numpy(image_pixels).unsqueeze(0).unsqueeze(0)

            tensor_image = tensor_image.to(self.device)
            if params["half_precision"]:
                tensor_image = tensor_image.half()

            if params["pre_pad_size"] > 0:
                tensor_image = torch.nn.functional.pad(tensor_image, (0, params["pre_pad_size"], 0, params["pre_pad_size"]), mode="reflect")

            with torch.inference_mode():
                if params["tile_size"] > 0:
                    upscaled_tensor = self._tile_process(tensor_image, params["tile_size"], params["tile_pad_size"], params["scale"])
                else:
                    upscaled_tensor = self.model(tensor_image)

            if params["pre_pad_size"] > 0:
                pad = params["pre_pad_size"] * params["scale"]
                upscaled_tensor = upscaled_tensor[:, :, :-pad, :-pad]

            upscaled_tensor = upscaled_tensor.squeeze(0).clamp(0, 1).permute(1, 2, 0).cpu().float()
            upscaled_pixels = (upscaled_tensor.numpy() * 255.0).round().astype(np.uint8)

            results.append(PILImage.fromarray(upscaled_pixels))

        return results

    def _tile_process(self, image: Tensor, tile_size: int, tile_pad_size: int, scale: int) -> Tensor:
        """Process image in tiles with reflect-padded borders to avoid seam artifacts."""
        import torch

        _, channels, h, w = image.shape

        if tile_size >= h and tile_size >= w:
            # Image is smaller than tile size, process normally
            return self.model(image)

        # Calculate number of tiles along each axis
        h_tiles = (h + tile_size - 1) // tile_size
        w_tiles = (w + tile_size - 1) // tile_size

        # Create output tensor at upscaled resolution
        output = torch.zeros(image.shape[0], channels, h * scale, w * scale, dtype=image.dtype, device=image.device)

        for i in range(h_tiles):
            for j in range(w_tiles):
                # Calculate tile boundaries (no overlap, just padding around each tile)
                start_h = i * tile_size
                end_h = min(start_h + tile_size, h)
                start_w = j * tile_size
                end_w = min(start_w + tile_size, w)

                # Expand the tile with padding (clipped to image bounds)
                pad_start_h = max(start_h - tile_pad_size, 0)
                pad_end_h = min(end_h + tile_pad_size, h)
                pad_start_w = max(start_w - tile_pad_size, 0)
                pad_end_w = min(end_w + tile_pad_size, w)

                # Extract padded tile
                tile = image[:, :, pad_start_h:pad_end_h, pad_start_w:pad_end_w]

                # Process tile
                with torch.inference_mode():
                    upscaled_tile = self.model(tile)

                # Trim the padded borders from the upscaled tile
                trim_top    = (start_h - pad_start_h) * scale
                trim_left   = (start_w - pad_start_w) * scale
                trim_bottom = trim_top  + (end_h - start_h) * scale
                trim_right  = trim_left + (end_w - start_w) * scale
                upscaled_tile = upscaled_tile[:, :, trim_top:trim_bottom, trim_left:trim_right]

                # Place result in output tensor
                out_start_h = start_h * scale
                out_start_w = start_w * scale
                out_end_h = end_h * scale
                out_end_w = end_w * scale
                output[:, :, out_start_h:out_end_h, out_start_w:out_end_w] = upscaled_tile

        return output

class EsrganImageUpscaleTaskService(ImageUpscaleTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[RRDBNet] = None
        self.device: Optional[torch.device] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "basicsr", "torch", "torchvision", "huggingface_hub" ]

    async def _load_model(self) -> None:
        self.model, self.device = self._load_pretrained_model()

    async def _unload_model(self) -> None:
        self.model = None
        self.device = None

    def _load_pretrained_model(self) -> Tuple[RRDBNet, torch.device]:
        from basicsr.archs.rrdbnet_arch import RRDBNet

        model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=self.config.scale)
        self._load_model_checkpoint(model, self._get_model_path())

        device = self._resolve_device()
        model = model.to(device)
        model.eval()

        return model, device

    async def _run(
        self,
        action: ModelActionConfig,
        context: ComponentActionContext,
        loop: asyncio.AbstractEventLoop
    ) -> Any:
        return await EsrganImageUpscaleTaskAction(action, self.model, self.device).run(context, loop)
