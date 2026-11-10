from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import ImageDeblurringModelActionConfig, ColorFormat, BlendMethod
from mindor.core.foundation.streaming.iterators import StreamIterator, StreamChunkIterator
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.utils.image import compose_with_alpha, has_alpha
from ...base import ComponentActionContext, ModelTaskComponentAction
from PIL import Image as PILImage

if TYPE_CHECKING:
    import torch

class ImageDeblurringTaskAction(ModelTaskComponentAction):
    def __init__(self, config: ImageDeblurringModelActionConfig, device: Optional[torch.device]):
        self.config: ImageDeblurringModelActionConfig = config
        self.device: Optional[torch.device] = device

    async def run(self, context: ComponentActionContext) -> Any:
        image      = await context.render_image(self.config.image)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(image, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(image, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_images in BatchSourceIterator(image, batch_size=batch_size or 1):
                    batch_results = await self._process_batch(batch_images, params, context.cancellation_token)
                    for result in batch_results:
                        context.register_source("result", result)
                        yield (await context.render_variable(self.config.output)) if not is_direct_output else result

            if isinstance(image, StreamChunkIterator) and image.is_fragmented:
                return StreamChunkIterator(_stream_output_generator(), is_fragmented=True)

            return _stream_output_generator()
        else:
            results: List[PILImage.Image] = []
            async for batch_images in BatchSourceIterator(image, batch_size=batch_size or 1):
                batch_results = await self._process_batch(batch_images, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _process_batch(
        self,
        images: List[PILImage.Image],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[PILImage.Image]:
        alphas = [ image.convert("RGBA").split()[-1] if has_alpha(image) else None for image in images ]
        images = [ self._normalize_image(image, params["color_format"]) for image in images ]

        images = await self._deblur_batch(images, params, cancellation_token)

        results: List[PILImage.Image] = []

        for image, alpha in zip(images, alphas):
            if alpha is not None:
                results.append(compose_with_alpha(image, alpha))
            else:
                results.append(image)

        return results

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        color_format        = await context.render_variable(self.config.color_format)
        tile_size           = await context.render_scalar(self.config.params.tile_size, int)
        tile_overlap        = await context.render_scalar(self.config.params.tile_overlap, int)
        blend               = await context.render_variable(self.config.params.blend)
        augmented_inference = await context.render_scalar(self.config.params.augmented_inference, bool)

        try:
            color_format = ColorFormat(color_format)
        except ValueError:
            raise ValueError(f"Unsupported color format: {color_format}")

        try:
            blend = BlendMethod(blend)
        except ValueError:
            raise ValueError(f"Unsupported blend method: {blend}")

        if tile_size and tile_overlap >= tile_size:
            raise ValueError(f"'tile_overlap' ({tile_overlap}) must be smaller than 'tile_size' ({tile_size}).")

        return {
            "color_format": color_format,
            "tile_size":    tile_size,
            "tile_overlap": tile_overlap,
            "blend":        blend,
            "augmented_inference": augmented_inference,
        }

    def _normalize_image(self, image: PILImage.Image, color_format: ColorFormat) -> PILImage.Image:
        if color_format == ColorFormat.RGB:
            return image.convert("RGB")

        if color_format == ColorFormat.BGR:
            r, g, b = image.convert("RGB").split()
            return PILImage.merge("RGB", (b, g, r))

        raise ValueError(f"Unsupported color format: {color_format}")

    @abstractmethod
    async def _deblur_batch(
        self,
        images: List[PILImage.Image],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[PILImage.Image]:
        pass
