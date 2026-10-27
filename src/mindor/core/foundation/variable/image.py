from typing import Optional, List, Union, Any
from collections.abc import AsyncIterator, AsyncIterable
from ..streaming.resources import StreamResource, read_stream_to_bytes
from ..streaming.image import load_image_from_stream, ImageStreamResource
from ..streaming.iterators import StreamIterator, StreamChunkIterator
from mindor.core.utils.files import get_file_extension, guess_file_extension
from mindor.core.utils.image import probe_format
from PIL import Image as PILImage
import asyncio

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
        item_is_list: bool = False,
        single_as_array: bool = False,
        as_stream: bool = False,
    ) -> Optional[Union[ImageArrayValue, List[Optional[ImageArrayValue]], AsyncIterator[Any]]]:
        """Render an image array (or a nested list of them, with ``item_is_list=True``).

        With ``item_is_list=False`` (default) each ``value`` element is a single
        image, and nested lists are interpreted as a batch of image arrays.
        With ``item_is_list=True`` each ``value`` element is itself a group of
        image refs; non-batch inputs collapse to one ``ImageArrayValue`` (unit)
        and nested lists become ``List[ImageArrayValue]``. ``ArrayValue`` is
        never added as an outer wrapper — it always means "one unit" elsewhere
        in the codebase.
        """
        # Fragmented streams (e.g. per-html frame streams) represent a single
        # logical image array delivered in pieces — fall through to
        # `_render_element_array` which wraps them into one streaming ImageArrayValue.
        if isinstance(value, (StreamIterator, AsyncIterator)) and not self._is_fragmented_stream(value):
            async def _iterate():
                async for chunk in value:
                    if item_is_list:
                        yield await self._render_element_array(chunk, single_as_array=True, as_stream=as_stream)
                    else:
                        yield await self._render_element_array(chunk, single_as_array, as_stream)

            # Preserve StreamChunkIterator type for downstream isinstance checks.
            if isinstance(value, StreamChunkIterator):
                return StreamChunkIterator(_iterate(), is_fragmented=value.is_fragmented)

            return _iterate()

        if item_is_list:
            if self._is_nested_element_array(value):
                return [ await self._render_element_array(item, single_as_array=True, as_stream=as_stream) for item in value ]

            if single_as_array and value is not None:
                # Explicit empty batch — pass through without promoting `[]` to a
                # unit group. "No images" is spelled `None` (handled by callers),
                # so `[]` here means the user asked for a zero-length batch axis.
                if isinstance(value, (list, tuple)) and len(value) == 0:
                    return []

                return [ await self._render_element_array(value, single_as_array=True, as_stream=as_stream) ]

            return None

        if self._is_nested_element_array(value):
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

        if self._is_fragmented_stream(value):
            async def _iterate():
                async for item in value:
                    image = await self._render_element(item, as_stream)
                    if image is not None:
                        yield image
            return ImageArrayValue(_iterate())

        if isinstance(value, (list, tuple)):
            return ImageArrayValue([ await self._render_element(item, as_stream) for item in value ])

        if single_as_array and value is not None:
            image = await self._render_element(value, as_stream)
            if image is not None:
                return ImageArrayValue([ image ], is_single=True)

        if value is not None:
            raise TypeError(
                f"expected an image array (list, ImageArrayValue, or fragmented stream) "
                f"but got a single image. Join a per-item stream with \"+\"."
            )

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
        else:
            if isinstance(value, PILImage.Image):
                return value

            if isinstance(value, ImageStreamResource):
                return await value.as_image()

            if isinstance(value, StreamResource):
                return await load_image_from_stream(value)

        if value is None:
            return None

        if isinstance(value, str):
            raise TypeError(
                f"image reference requires an explicit format hint: use "
                f"`as image;path`, `as image;url`, `as image;base64`, or `as image;data-uri`."
            )

        raise TypeError(f"`image` requires an image or raw image bytes, got {value.__class__.__name__}")

    def _is_nested_element_array(self, value: Any) -> bool:
        """True when ``value`` is a list of element arrays — a top-level
        list whose first item is itself an element array or a fragmented
        stream.
        """
        return (
            isinstance(value, (list, tuple))
            and bool(value)
            and (self._is_element_array(value[0]) or self._is_fragmented_stream(value[0]))
        )

    def _is_element_array(self, value: Any) -> bool:
        """True when ``value`` is a batch of image refs — a list/tuple of
        refs or an already-materialized ``ImageArrayValue``.
        """
        return isinstance(value, (list, tuple, ImageArrayValue))

    def _is_fragmented_stream(self, value: Any) -> bool:
        """True when ``value`` is a fragmented ``StreamChunkIterator`` — one
        logical image array delivered in pieces.
        """
        return isinstance(value, StreamChunkIterator) and value.is_fragmented
