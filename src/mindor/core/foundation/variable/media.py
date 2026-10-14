from typing import List, Optional, Union, Any
from collections.abc import AsyncIterator, AsyncIterable
from ..streaming.media import MediaSource, create_media_source
from ..streaming.iterators import StreamIterator, StreamChunkIterator

class MediaArrayValue:
    """A materialized or streaming array of media sources.

    Backed by either a `List[MediaSource]` (re-iterable) or an
    `AsyncIterable[MediaSource]` (one-shot). Consumers use `async for` to
    iterate lazily, or `await collect()` when the full list is needed.
    """
    def __init__(self, source: Union[List[MediaSource], AsyncIterable[MediaSource]], is_single: bool = False):
        self.source: Union[List[MediaSource], AsyncIterable[MediaSource]] = source
        self.is_single: bool = is_single

    def __aiter__(self) -> AsyncIterator[MediaSource]:
        if isinstance(self.source, list):
            async def _iterate():
                for item in self.source:
                    yield item
            return _iterate()

        return self.source.__aiter__()

    async def collect(self) -> List[MediaSource]:
        if isinstance(self.source, AsyncIterable):
            return [ item async for item in self.source ]

        return self.source

class MediaValueRenderer:
    async def render_array(
        self,
        value: Any,
        item_is_list: bool = False,
        single_as_array: bool = False,
    ) -> Optional[Union[MediaArrayValue, List[Optional[MediaArrayValue]], AsyncIterator[Any]]]:
        """Render a media array (or a nested list of them, with ``item_is_list=True``).

        With ``item_is_list=False`` (default) each ``value`` element is a single
        media source, and nested lists are interpreted as a batch of media arrays.
        With ``item_is_list=True`` each ``value`` element is itself a group of
        media refs; the batch axis is always an explicit Python list, with
        non-batch inputs collapsing to a one-element list.
        """
        # Fragmented streams represent a single logical media array delivered
        # in pieces — fall through to `_render_element_array` which wraps them
        # into one streaming MediaArrayValue.
        if isinstance(value, (StreamIterator, AsyncIterator)) and not self._is_fragmented_stream(value):
            async def _iterate():
                async for chunk in value:
                    if item_is_list:
                        yield await self._render_element_array(chunk, single_as_array=True)
                    else:
                        yield await self._render_element_array(chunk, single_as_array)

            # Preserve StreamChunkIterator type for downstream isinstance checks.
            if isinstance(value, StreamChunkIterator):
                return StreamChunkIterator(_iterate(), is_fragmented=value.is_fragmented)

            return _iterate()

        if item_is_list:
            if self._is_nested_element_array(value):
                return [ await self._render_element_array(item, single_as_array=True) for item in value ]

            if single_as_array and value is not None:
                return [ await self._render_element_array(value, single_as_array=True) ]

            return None

        if self._is_nested_element_array(value):
            return [ await self._render_element_array(item, single_as_array) for item in value ]

        return await self._render_element_array(value, single_as_array)

    async def render(
        self,
        value: Any
    ) -> Optional[Union[MediaSource, List[Optional[MediaSource]], AsyncIterator[Optional[MediaSource]]]]:
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

    async def _render_element_array(self, value: Any, single_as_array: bool = False) -> Optional[MediaArrayValue]:
        if isinstance(value, MediaArrayValue):
            return value

        if self._is_fragmented_stream(value):
            async def _iterate():
                async for item in value:
                    media = await self._render_element(item)
                    if media is not None:
                        yield media
            return MediaArrayValue(_iterate())

        if isinstance(value, (list, tuple)):
            return MediaArrayValue([ await self._render_element(item) for item in value ])

        if single_as_array and value is not None:
            media = await self._render_element(value)
            if media is not None:
                return MediaArrayValue([ media ], is_single=True)

        if value is not None:
            raise TypeError(
                f"expected a media array (list, MediaArrayValue, or fragmented stream) "
                f"but got a single media. Join a per-item stream with \"+\"."
            )

        return None

    async def _render_element(self, value: Any) -> Optional[MediaSource]:
        if value is not None:
            return create_media_source(value)

        return None

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
        """True when ``value`` is a batch of media refs — a list/tuple of
        refs or an already-materialized ``MediaArrayValue``.
        """
        return isinstance(value, (list, tuple, MediaArrayValue))

    def _is_fragmented_stream(self, value: Any) -> bool:
        """True when ``value`` is a fragmented ``StreamChunkIterator`` — one
        logical media array delivered in pieces.
        """
        return isinstance(value, StreamChunkIterator) and value.is_fragmented
