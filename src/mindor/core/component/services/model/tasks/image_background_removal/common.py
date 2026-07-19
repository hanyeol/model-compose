from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import ImageBackgroundRemovalModelActionConfig, BackgroundRemovalOutputFormat
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamIterator
from ...base import ModelTaskService, ComponentActionContext
from PIL import Image as PILImage
import asyncio

if TYPE_CHECKING:
    import torch

class ImageBackgroundRemovalTaskAction:
    def __init__(self, config: ImageBackgroundRemovalModelActionConfig, device: Optional[torch.device]):
        self.config: ImageBackgroundRemovalModelActionConfig = config
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
                    batch_images = [ self._normalize_image(image) for image in batch_images ]
                    batch_masks = self._predict_masks(batch_images, params, context.cancellation_token)
                    for image, mask in zip(batch_images, batch_masks):
                        yield self._render_output(image, mask, params["output_format"])

            return _stream_output_generator()
        else:
            results: List[PILImage.Image] = []
            async for batch_images in BatchSourceIterator(image, batch_size=batch_size or 1):
                batch_images = [ self._normalize_image(image) for image in batch_images ]
                batch_masks = self._predict_masks(batch_images, params, context.cancellation_token)
                for image, mask in zip(batch_images, batch_masks):
                    results.append(self._render_output(image, mask, params["output_format"]))

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        output_format = await context.render_variable(self.config.output_format)

        return {
            "output_format": output_format,
        }

    def _normalize_image(self, image: PILImage.Image) -> PILImage.Image:
        return image.convert("RGB")

    def _render_output(self, image: PILImage.Image, mask: PILImage.Image, output_format: BackgroundRemovalOutputFormat) -> PILImage.Image:
        if output_format == BackgroundRemovalOutputFormat.RGBA:
            resized_mask = mask.resize(image.size, PILImage.Resampling.BILINEAR) if mask.size != image.size else mask
            rgba = image.convert("RGBA")
            rgba.putalpha(resized_mask)
            return rgba

        if output_format == BackgroundRemovalOutputFormat.MASK:
            return mask

        raise ValueError(f"Unsupported output format: {output_format}")

    @abstractmethod
    def _predict_masks(
        self,
        images: List[PILImage.Image],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None
    ) -> List[PILImage.Image]:
        pass

class ImageBackgroundRemovalTaskService(ModelTaskService):
    pass
