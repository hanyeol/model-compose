from __future__ import annotations

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import ImageCompressorActionConfig
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.logger import logging
from ..base import ComponentActionContext
from ....action.base import ComponentAction
from PIL import Image as PILImage
import io, asyncio

class ImageCompressorAction(ComponentAction):
    def __init__(self, config: ImageCompressorActionConfig):
        self.config: ImageCompressorActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        image      = await context.render_image(self.config.image)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(image, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(image, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_images in BatchSourceIterator(image, batch_size=batch_size or 1):
                    batch_results = await self._compress_batch(batch_images, params)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results = []
            async for batch_images in BatchSourceIterator(image, batch_size=batch_size or 1):
                batch_results = await self._compress_batch(batch_images, params)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        return {}

    async def _compress_batch(
        self,
        images: List[Optional[PILImage.Image]],
        params: Dict[str, Any],
    ) -> List[Optional[bytes]]:
        async def _compress(image: Optional[PILImage.Image]) -> Optional[bytes]:
            if image is None:
                logging.debug("Image compressor skipped because no image was provided.")
                return None

            return await self._compress(image, params)

        return await asyncio.gather(*[ _compress(image) for image in images ])

    @abstractmethod
    async def _compress(self, image: PILImage.Image, params: Dict[str, Any]) -> bytes:
        pass

    @staticmethod
    def _encode_png_lossless(image: PILImage.Image, compress_level: int, strip_metadata: bool) -> bytes:
        save_params: Dict[str, Any] = {
            "format": "PNG",
            "optimize": True,
            "compress_level": compress_level,
        }

        if not strip_metadata and image.info:
            pnginfo = ImageCompressorAction._build_pnginfo(image.info)

            if pnginfo is not None:
                save_params["pnginfo"] = pnginfo

        buffer = io.BytesIO()
        image.save(buffer, **save_params)

        return buffer.getvalue()

    @staticmethod
    def _build_pnginfo(info: Dict[str, Any]) -> Optional[Any]:
        from PIL import PngImagePlugin

        pnginfo = PngImagePlugin.PngInfo()
        added = False

        for key, value in info.items():
            if isinstance(value, str):
                pnginfo.add_text(key, value)
                added = True

        return pnginfo if added else None
