from typing import Optional, List, Union, Any
from collections.abc import AsyncIterator, AsyncIterable
from ..streaming.resources import StreamResource
from ..streaming.image import load_image_from_stream, ImageStreamResource
from ..streaming.iterators import StreamIterator, StreamChunkIterator
from PIL import Image as PILImage

ImageValue = Union[PILImage.Image, ImageStreamResource]

class ImageArrayValue:
    """A materialized or streaming array of images.

    All elements share one type — either `PIL.Image` or `ImageStreamResource`
    — chosen by the renderer that produced this value (see the `as_stream`
    argument to `ImageValueRenderer.render_array`). Elements are already
    normalized before they reach this container; iteration and `collect()`
    do not do any per-item conversion.
    """
    def __init__(
        self,
        source: Union[List[ImageValue], AsyncIterable[ImageValue]],
        is_single: bool = False,
    ):
        self.source: Union[List[ImageValue], AsyncIterable[ImageValue]] = source
        self.is_single: bool = is_single

    def __aiter__(self) -> AsyncIterator[ImageValue]:
        if isinstance(self.source, list):
            async def _iterate():
                for item in self.source:
                    yield item
            return _iterate()

        return self.source.__aiter__()

    async def collect(self) -> List[ImageValue]:
        if isinstance(self.source, AsyncIterable):
            return [ item async for item in self.source ]

        return self.source

class ImageValueRenderer:
    async def render_array(
        self,
        value: Any,
        single_as_array: bool = False,
        as_stream: bool = False,
    ) -> Optional[Union[ImageArrayValue, List[Optional[ImageArrayValue]], AsyncIterator[Optional[ImageArrayValue]]]]:
        # Fragmented streams (e.g. per-html frame streams) represent a single
        # logical image array delivered in pieces — fall through to
        # `_render_element_array` which wraps them into one streaming ImageArrayValue.
        is_fragmented_stream = isinstance(value, StreamChunkIterator) and value.is_fragmented

        if isinstance(value, (StreamIterator, AsyncIterator)) and not is_fragmented_stream:
            async def _iterate():
                async for chunk in value:
                    yield await self._render_element_array(chunk, single_as_array, as_stream)

            # Preserve StreamChunkIterator type for downstream isinstance checks.
            if isinstance(value, StreamChunkIterator):
                return StreamChunkIterator(_iterate(), is_fragmented=value.is_fragmented)

            return _iterate()

        if isinstance(value, (list, tuple)) and value and isinstance(value[0], (list, tuple, StreamChunkIterator)):
            return [ await self._render_element_array(item, single_as_array, as_stream) for item in value ]

        return await self._render_element_array(value, single_as_array, as_stream)

    async def render(
        self,
        value: Any,
        as_stream: bool = False,
    ) -> Optional[Union[ImageValue, List[Optional[ImageValue]], AsyncIterator[Optional[ImageValue]]]]:
        if isinstance(value, (StreamIterator, AsyncIterator)):
            async def _iterate():
                async for chunk in value:
                    yield await self._render_element(chunk, as_stream)

            # Preserve StreamChunkIterator type for downstream isinstance checks.
            if isinstance(value, StreamChunkIterator):
                return StreamChunkIterator(_iterate(), is_fragmented=value.is_fragmented)

            return _iterate()

        if isinstance(value, (list, tuple)):
            return [ await self._render_element(item, as_stream) for item in value ]

        return await self._render_element(value, as_stream)

    async def _render_element_array(
        self,
        value: Any,
        single_as_array: bool = False,
        as_stream: bool = False,
    ) -> Optional[ImageArrayValue]:
        if isinstance(value, ImageArrayValue):
            # Re-coerce lazily to the requested element contract.
            async def _iterate():
                async for item in value:
                    image = await self._render_element(item, as_stream)
                    if image is not None:
                        yield image
            return ImageArrayValue(_iterate(), is_single=value.is_single)

        if isinstance(value, StreamChunkIterator) and value.is_fragmented:
            async def _iterate():
                async for item in value:
                    image = await self._render_element(item, as_stream)
                    if image is not None:
                        yield image
            return ImageArrayValue(_iterate())

        if isinstance(value, (list, tuple)):
            return ImageArrayValue([ await self._render_element(item, as_stream) for item in value ])

        if single_as_array:
            image = await self._render_element(value, as_stream)
            if image is not None:
                return ImageArrayValue([ image ], is_single=True)

        return None

    async def _render_element(self, value: Any, as_stream: bool = False) -> Optional[ImageValue]:
        """Normalize a raw value to the requested element type. `as_stream`
        picks the target: `PIL.Image` (default) or `ImageStreamResource`.
        """
        if as_stream:
            if isinstance(value, ImageStreamResource):
                return value

            if isinstance(value, PILImage.Image):
                return ImageStreamResource(value, "png")

            if isinstance(value, StreamResource):
                return ImageStreamResource(await load_image_from_stream(value), "png")

            return None

        if isinstance(value, PILImage.Image):
            return value

        if isinstance(value, ImageStreamResource):
            return await value.as_image()

        if isinstance(value, StreamResource):
            return await load_image_from_stream(value)

        return None
