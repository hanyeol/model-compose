from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, SwinIRImageUpscaleModelActionConfig
from mindor.core.logger import logging
from ..common import ImageUpscaleTaskService, ImageUpscaleTaskAction
from ....base import ComponentActionContext
from PIL import Image as PILImage
import asyncio

if TYPE_CHECKING:
    from basicsr.archs.swinir_arch import SwinIR
    from torch import Tensor
    import torch

class SwinIRImageUpscaleTaskAction(ImageUpscaleTaskAction):
    config: SwinIRImageUpscaleModelActionConfig

    def __init__(
        self,
        config: SwinIRImageUpscaleModelActionConfig,
        model: SwinIR,
        device: Optional[torch.device]
    ):
        super().__init__(config, device)

        self.model: SwinIR = model

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        task         = await context.render_variable(self.config.params.task)
        tile_size    = await context.render_variable(self.config.params.tile_size)
        tile_overlap = await context.render_variable(self.config.params.tile_overlap)
        scale        = await context.render_variable(self.config.params.scale)
        window_size  = await context.render_variable(self.config.params.window_size)
        jpeg_quality = await context.render_variable(self.config.params.jpeg_quality)

        params.update({
            "task":         task,
            "tile_size":    tile_size,
            "tile_overlap": tile_overlap,
            "scale":        scale,
            "window_size":  window_size,
            "jpeg_quality": jpeg_quality,
        })

        return params

    def _upscale(self, images: List[PILImage.Image], params: Dict[str, Any]) -> List[PILImage.Image]:
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

            if params["task"] == "dn":
                pass

            if params["task"] == "jpeg_car" and params["jpeg_quality"] < 100:
                pass

            with torch.no_grad():
                if params["tile_size"] > 0:
                    upscaled_tensor = self._tile_process(tensor_image, params["tile_size"], params["tile_overlap"], params["scale"])
                else:
                    upscaled_tensor = self.model(tensor_image)

            upscaled_tensor = upscaled_tensor.squeeze(0).permute(1, 2, 0).cpu()
            upscaled_pixels = (upscaled_tensor.numpy() * 255.0).clip(0, 255).astype(np.uint8)

            results.append(PILImage.fromarray(upscaled_pixels))

        return results

    def _tile_process(self, image: Tensor, tile_size: int, tile_overlap: int, scale: int) -> Tensor:
        """Process image in tiles with overlap for SwinIR."""
        import torch

        _, _, h, w = image.shape

        if tile_size >= h and tile_size >= w:
            # Image is smaller than tile size, process normally
            return self.model(image)

        # Calculate stride (tile_size - overlap)
        stride = tile_size - tile_overlap

        # Calculate number of tiles
        h_tiles = (h - tile_overlap + stride - 1) // stride
        w_tiles = (w - tile_overlap + stride - 1) // stride

        # Create output tensor
        output_h = h * scale
        output_w = w * scale
        output = torch.zeros(image.shape[0], image.shape[1], output_h, output_w).to(image.device)

        for i in range(h_tiles):
            for j in range(w_tiles):
                # Calculate tile boundaries
                start_h = i * stride
                end_h = min(start_h + tile_size, h)
                start_w = j * stride
                end_w = min(start_w + tile_size, w)

                # Extract tile
                tile = image[:, :, start_h:end_h, start_w:end_w]

                # Process tile
                with torch.no_grad():
                    upscaled_tile: Tensor = self.model(tile)

                # Calculate output position
                out_start_h = start_h * scale
                out_end_h = end_h * scale
                out_start_w = start_w * scale
                out_end_w = end_w * scale

                # Handle overlap blending
                if i > 0 or j > 0:
                    # Blend overlapping regions
                    overlap_h = tile_overlap * scale if i > 0 else 0
                    overlap_w = tile_overlap * scale if j > 0 else 0

                    # Simple averaging for overlap regions
                    if overlap_h > 0:
                        blend_start_h = out_start_h
                        blend_end_h = out_start_h + overlap_h
                        output[:, :, blend_start_h:blend_end_h, out_start_w:out_end_w] = \
                            (output[:, :, blend_start_h:blend_end_h, out_start_w:out_end_w] +
                             upscaled_tile[:, :, :overlap_h, :]) / 2
                        upscaled_tile = upscaled_tile[:, :, overlap_h:, :]
                        out_start_h += overlap_h

                    if overlap_w > 0:
                        blend_start_w = out_start_w
                        blend_end_w = out_start_w + overlap_w
                        output[:, :, out_start_h:out_end_h, blend_start_w:blend_end_w] = \
                            (output[:, :, out_start_h:out_end_h, blend_start_w:blend_end_w] +
                             upscaled_tile[:, :, :, :overlap_w]) / 2
                        upscaled_tile = upscaled_tile[:, :, :, overlap_w:]
                        out_start_w += overlap_w

                # Place result in output tensor
                tile_h, tile_w = upscaled_tile.shape[2], upscaled_tile.shape[3]
                output[:, :, out_start_h:out_start_h+tile_h, out_start_w:out_start_w+tile_w] = upscaled_tile

        return output

class SwinIRImageUpscaleTaskService(ImageUpscaleTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[SwinIR] = None
        self.device: Optional[torch.device] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "basicsr", "torch", "torchvision", "huggingface_hub" ]

    async def _load_model(self) -> None:
        self.model, self.device = self._load_pretrained_model()

    async def _unload_model(self) -> None:
        self.model = None
        self.device = None

    def _load_pretrained_model(self) -> Tuple[SwinIR, torch.device]:
        from basicsr.archs.swinir_arch import SwinIR

        model = SwinIR(**self._get_model_params())
        self._load_model_checkpoint(model, self._get_model_path())

        device = self._resolve_device(self.config.device)
        model = model.to(device)
        model.eval()

        return model, device

    def _get_model_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {}

        return params

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        return await SwinIRImageUpscaleTaskAction(action, self.model, self.device).run(context, loop)
