from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, TypeAlias, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, RealEsrganImageUpscaleModelActionConfig
from mindor.core.logger import logging
from .common import ImageUpscaleTaskService, ImageUpscaleTaskAction
from ...base import ComponentActionContext
from PIL import Image as PILImage
import asyncio

if TYPE_CHECKING:
    from RealESRGAN import RealESRGAN
    import torch

class RealEsrganImageUpscaleTaskAction(ImageUpscaleTaskAction):
    def __init__(self, config: RealEsrganImageUpscaleModelActionConfig, model: RealESRGAN, device: torch.device):
        super().__init__(config, device)

        self.model: RealESRGAN = model

    async def _upscale(self, images: List[PILImage.Image], params: Dict[str, Any]) -> List[PILImage.Image]:
        import numpy as np

        upscaled_images = []
        for image in images:
            upscaled_image = self.model.predict(np.array(image), **params)
            upscaled_images.append(upscaled_image)

        return upscaled_images

    async def _resolve_upscale_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params: Dict[str, Any] = {}

        params["batch_size"  ] = await context.render_variable(self.config.params.tile_batch_size)
        params["patches_size"] = await context.render_variable(self.config.params.tile_size)
        params["padding"     ] = await context.render_variable(self.config.params.tile_pad_size)
        params["pad_size"    ] = await context.render_variable(self.config.params.pre_pad_size)

        return params

class RealEsrganImageUpscaleTaskService(ImageUpscaleTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[RealESRGAN] = None
        self.device: Optional[torch.device] = None

        self._patch_huggingface_hub_compatibility()

    def _patch_huggingface_hub_compatibility(self) -> None:
        import huggingface_hub as hub
        if not hasattr(hub, "cached_download"):
            def cached_download(*args, **kwargs):
                raise NotImplementedError("cached_download is deprecated; not intended to be used.")
            hub.cached_download = cached_download

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "realesrgan>=1.0@git+https://github.com/sberbank-ai/Real-ESRGAN.git" ]

    async def _serve(self) -> None:
        try:
            self.model, self.device = self._load_pretrained_model()
            logging.info(f"Model loaded successfully on device '{self.device}': {self.config.model}")
        except Exception as e:
            logging.error(f"Failed to load model '{self.config.model}': {e}")
            raise

    async def _shutdown(self) -> None:
        self.model = None
        self.device = None

    def _load_pretrained_model(self) -> Tuple[RealESRGAN, torch.device]:
        from RealESRGAN import RealESRGAN

        device = self._resolve_device()
        model = RealESRGAN(device=device, scale=self.config.scale)
        model.load_weights(self._get_model_path())

        return model, device

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        return await RealEsrganImageUpscaleTaskAction(action, self.model, self.device).run(context)
