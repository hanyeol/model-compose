from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Literal, Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import ImageUpscaleModelActionConfig, ColorFormat
from mindor.core.logger import logging
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamIterator
from ...base import ModelTaskService, ComponentActionContext
from PIL import Image as PILImage
import asyncio

if TYPE_CHECKING:
    import torch

_RESAMPLE_MAP = {
    "bicubic": PILImage.Resampling.BICUBIC,
    "lanczos": PILImage.Resampling.LANCZOS,
}

class ImageUpscaleTaskAction:
    def __init__(self, config: ImageUpscaleModelActionConfig, device: Optional[torch.device]):
        self.config: ImageUpscaleModelActionConfig = config
        self.device: Optional[torch.device] = device

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        image      = await context.render_image(self.config.image)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(image, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(image, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_images in BatchSourceIterator(image, batch_size=batch_size or 1):
                    batch_images = [ self._normalize_image(img, params["color_format"]) for img in batch_images ]
                    batch_results = await self._upscale(batch_images, params, loop)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results: List[PILImage.Image] = []
            async for batch_images in BatchSourceIterator(image, batch_size=batch_size or 1):
                batch_images = [ self._normalize_image(img, params["color_format"]) for img in batch_images ]
                batch_results = await self._upscale(batch_images, params, loop)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        color_format = await context.render_variable(self.config.color_format)

        return {
            "color_format": color_format,
        }

    def _normalize_image(self, image: PILImage.Image, color_format: ColorFormat) -> PILImage.Image:
        if color_format == ColorFormat.RGB:
            return image.convert("RGB")

        if color_format == ColorFormat.BGR:
            r, g, b = image.convert("RGB").split()
            return PILImage.merge("RGB", (b, g, r))

        raise ValueError(f"Unsupported color format: {color_format}")

    def _downsample_image(self, image: PILImage.Image, method: Literal[ "lanczos", "bicubic" ], scale: int = 4) -> PILImage.Image:
        downsample_size = (max(1, image.size[0] // scale), max(1, image.size[1] // scale))

        if method not in _RESAMPLE_MAP:
            logging.warning(f"Unsupported downsample method: {method}. fallback to 'lanczos' method")
            resample = PILImage.Resampling.LANCZOS
        else:
            resample = _RESAMPLE_MAP[method]

        return image.resize(downsample_size, resample)

    @abstractmethod
    async def _upscale(self, images: List[PILImage.Image], params: Dict[str, Any], loop: asyncio.AbstractEventLoop) -> List[PILImage.Image]:
        pass

class ImageUpscaleTaskService(ModelTaskService):
    pass
