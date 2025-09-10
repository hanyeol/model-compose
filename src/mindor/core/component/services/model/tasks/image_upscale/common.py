from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, TypeAlias, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.action import ImageUpscaleModelActionConfig, ColorFormat
from mindor.core.logger import logging
from ...base import ModelTaskService, ComponentActionContext
from PIL import Image as PILImage

if TYPE_CHECKING:
    import torch

_resample_map = {
    "bicubic": PILImage.Resampling.BICUBIC,
    "lanczos": PILImage.Resampling.LANCZOS,
}

class ImageUpscaleTaskAction:
    def __init__(self, config: ImageUpscaleModelActionConfig, device: torch.device):
        self.config: ImageUpscaleModelActionConfig = config
        self.device: torch.device = device

    async def run(self, context: ComponentActionContext) -> Any:
        image = await self._prepare_input(context)
        is_single_input = not isinstance(image, list)
        images: List[PILImage.Image] = [ image ] if is_single_input else image
        results = []

        batch_size   = await context.render_variable(self.config.batch_size)
        color_format = await context.render_variable(self.config.params.color_format)
        params       = await self._resolve_upscale_params(context)

        for index in range(0, len(images), batch_size):
            batch_images = [ self._normalize_image(image, color_format) for image in images[index:index + batch_size] ]
            upscaled_images = await self._upscale(batch_images, params)
            results.extend(upscaled_images)

        return results[0] if is_single_input else results

    async def _prepare_input(self, context: ComponentActionContext) -> Union[PILImage.Image, List[PILImage.Image]]:
        return await context.render_image(self.config.image)

    def _normalize_image(self, image: PILImage.Image, color_format: ColorFormat) -> PILImage.Image:
        if color_format == ColorFormat.RGB:
            return image.convert("RGB")

        if color_format == ColorFormat.BGR:
            r, g, b = image.convert("RGB").split()
            return PILImage.merge("RGB", (b, g, r))
        
        raise ValueError(f"Unsupported color format: {color_format}")

    def _downsample_image(self, image: PILImage.Image, method: Literal["lanczos", "bicubic"], scale: int = 4) -> PILImage.Image:
        downsample_size = (max(1, image.size[0] // scale), max(1, image.size[1] // scale))
        
        if method not in _resample_map:
            logging.warning(f"Unsupported downsample method: {method}. fallback to 'lanczos' method")
            resample = PILImage.Resampling.LANCZOS
        else:
            resample = _resample_map[method]

        return image.resize(downsample_size, resample)

    @abstractmethod
    async def _upscale(self, images: List[PILImage.Image], params: Dict[str, Any]) -> List[PILImage.Image]:
        pass

    @abstractmethod
    async def _resolve_upscale_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        pass

class ImageUpscaleTaskService(ModelTaskService):
    pass
