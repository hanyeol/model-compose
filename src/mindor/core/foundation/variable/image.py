from typing import Optional, List, Union, Any
from collections.abc import AsyncIterator, AsyncIterable
from ..streaming.resources import StreamResource
from ..streaming.image import load_image_from_stream, ImageStreamResource
from ..streaming.iterators import StreamIterator, StreamChunkIterator
from PIL import Image as PILImage

class ImageArrayValue:
    """A materialized or streaming array of images.

    Backed by either a `List[PILImage.Image]` (re-iterable) or an
    `AsyncIterable[PILImage.Image]` (one-shot). Consumers use `async for` to
    iterate lazily, or `await collect()` when the full list is needed.
    """
    def __init__(self, source: Union[List[PILImage.Image], AsyncIterable[PILImage.Image]]):
        self.source: Union[List[PILImage.Image], AsyncIterable[PILImage.Image]] = source

    def __aiter__(self) -> AsyncIterator[PILImage.Image]:
        if isinstance(self.source, list):
            async def _iterate():
                for item in self.source:
                    yield item
            return _iterate()

        return self.source.__aiter__()

    async def collect(self) -> List[PILImage.Image]:
        if isinstance(self.source, list):
            return self.source

        return [ item async for item in self.source ]

class ImageValueRenderer:
    async def render_array(
        self,
        value: Any
    ) -> Optional[Union[ImageArrayValue, List[Optional[ImageArrayValue]], AsyncIterator[Optional[ImageArrayValue]]]]:
        # Fragmented streams (e.g. per-html frame streams) represent a single
        # logical image array delivered in pieces — fall through to
        # `_render_element_array` which wraps them into one streaming ImageArrayValue.
        is_fragmented_stream = isinstance(value, StreamChunkIterator) and value.is_fragmented

        if isinstance(value, (StreamIterator, AsyncIterator)) and not is_fragmented_stream:
            async def _iterate():
                async for chunk in value:
                    yield await self._render_element_array(chunk)

            # Preserve StreamChunkIterator type for downstream isinstance checks.
            if isinstance(value, StreamChunkIterator):
                return StreamChunkIterator(_iterate(), is_fragmented=value.is_fragmented)

            return _iterate()

        if isinstance(value, (list, tuple)) and value and isinstance(value[0], (list, tuple, StreamChunkIterator)):
            return [ await self._render_element_array(item) for item in value ]

        return await self._render_element_array(value)

    async def render(
        self,
        value: Any
    ) -> Optional[Union[PILImage.Image, List[Optional[PILImage.Image]], AsyncIterator[Optional[PILImage.Image]]]]:
        if isinstance(value, (StreamIterator, AsyncIterator)):
            async def _iterate():
                async for chunk in value:
                    yield await self._render_element(chunk)

            # Preserve StreamChunkIterator type for downstream isinstance checks.
            if isinstance(value, StreamChunkIterator):
                return StreamChunkIterator(_iterate(), is_fragmented=value.is_fragmented)

            return _iterate()

        if isinstance(value, (list, tuple)):
            return [ await self._render_element(item) for item in value ]

        return await self._render_element(value)

    async def _render_element_array(self, value: Any) -> Optional[ImageArrayValue]:
        if isinstance(value, ImageArrayValue):
            return value

        if isinstance(value, StreamChunkIterator) and value.is_fragmented:
            async def _iterate():
                async for item in value:
                    image = await self._render_element(item)
                    if image is not None:
                        yield image
            return ImageArrayValue(_iterate())

        if isinstance(value, (list, tuple)):
            return ImageArrayValue([ await self._render_element(item) for item in value ])

        return None

    async def _render_element(self, value: Any) -> Optional[PILImage.Image]:
        if isinstance(value, PILImage.Image):
            return value

        if isinstance(value, ImageStreamResource):
            return value.image

        if isinstance(value, StreamResource):
            return await load_image_from_stream(value)

        return None
