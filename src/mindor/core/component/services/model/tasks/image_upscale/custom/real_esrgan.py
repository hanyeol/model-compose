from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, RealEsrganImageUpscaleModelActionConfig
from mindor.core.logger import logging
from ..common import ImageUpscaleTaskService, ImageUpscaleTaskAction
from ....base import ComponentActionContext
from PIL import Image as PILImage
import asyncio

if TYPE_CHECKING:
    from RealESRGAN import RealESRGAN
    import torch

class RealEsrganImageUpscaleTaskAction(ImageUpscaleTaskAction):
    def __init__(
        self,
        config: RealEsrganImageUpscaleModelActionConfig,
        model: RealESRGAN,
        device: Optional[torch.device]
    ):
        super().__init__(config, device)

        self.config: RealEsrganImageUpscaleModelActionConfig = config
        self.model: RealESRGAN = model

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        tile_batch_size = await context.render_variable(self.config.params.tile_batch_size)
        tile_size       = await context.render_variable(self.config.params.tile_size)
        tile_pad_size   = await context.render_variable(self.config.params.tile_pad_size)
        pre_pad_size    = await context.render_variable(self.config.params.pre_pad_size)

        params.update({
            "batch_size":   tile_batch_size,
            "patches_size": tile_size,
            "padding":      tile_pad_size,
            "pad_size":     pre_pad_size,
        })

        return params

    async def _upscale(self, images: List[PILImage.Image], params: Dict[str, Any], loop: asyncio.AbstractEventLoop) -> List[PILImage.Image]:
        return await loop.run_in_executor(None, self._upscale_batch, images, params)

    def _upscale_batch(self, images: List[PILImage.Image], params: Dict[str, Any]) -> List[PILImage.Image]:
        import numpy as np

        upscaled_images: List[PILImage.Image] = []

        for image in images:
            upscaled_images.append(self.model.predict(
                np.array(image),
                batch_size=params["batch_size"],
                patches_size=params["patches_size"],
                padding=params["padding"],
                pad_size=params["pad_size"],
            ))

        return upscaled_images

class RealEsrganImageUpscaleTaskService(ImageUpscaleTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[RealESRGAN] = None
        self.device: Optional[torch.device] = None

        self._patch_huggingface_hub_compatibility()

    def _patch_huggingface_hub_compatibility(self) -> None:
        import huggingface_hub as hub

        if not hasattr(hub, "cached_download"):
            def _raise_not_implemented(*args, **kwargs):
                raise NotImplementedError("cached_download is deprecated; not intended to be used.")
            hub.cached_download = _raise_not_implemented

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "realesrgan>=1.0@git+https://github.com/sberbank-ai/Real-ESRGAN.git" ]

    async def _load_model(self) -> None:
        self.model, self.device = self._load_pretrained_model()

    async def _unload_model(self) -> None:
        self.model = None
        self.device = None

    def _load_pretrained_model(self) -> Tuple[RealESRGAN, torch.device]:
        from RealESRGAN import RealESRGAN

        device = self._resolve_device()
        model = RealESRGAN(device=device, scale=self.config.scale)
        model.load_weights(self._get_model_path())

        return model, device

    async def _run(
        self,
        action: ModelActionConfig,
        context: ComponentActionContext,
        loop: asyncio.AbstractEventLoop
    ) -> Any:
        return await RealEsrganImageUpscaleTaskAction(action, self.model, self.device).run(context, loop)
