from typing import List, Optional, Union, Any
from collections.abc import AsyncIterator, AsyncIterable
from ..streaming.video import create_video_source
from ..streaming.media import MediaSource
from ..streaming.iterators import StreamIterator, StreamChunkIterator
from .array import ArrayValue

class VideoArrayValue:
    """A materialized or streaming array of video sources.

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

class VideoValueRenderer:
    async def render_array(
        self,
        value: Any,
        item_is_list: bool = False,
        single_as_array: bool = False,
    ) -> Optional[Union[VideoArrayValue, ArrayValue, List[Any], AsyncIterator[Any]]]:
        """Render a video array (or a nested list of them, with ``item_is_list=True``).

        Mirrors ``ImageValueRenderer.render_array``'s matrix: outer axis is a
        batch; ``item_is_list=True`` makes each batch element a group
        (``VideoArrayValue``) and wraps the batch in an ``ArrayValue``.
        """
        # Fragmented streams represent a single logical video array delivered
        # in pieces — fall through to `_render_element_array` which wraps them
        # into one streaming VideoArrayValue.
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
                groups = [ await self._render_element_array(item, single_as_array=True) for item in value ]
                return ArrayValue(groups)

            if single_as_array and value is not None:
                group = await self._render_element_array(value, single_as_array=True)
                return ArrayValue([ group ] if group is not None else [], is_single=True)

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

    async def _render_element_array(self, value: Any, single_as_array: bool = False) -> Optional[VideoArrayValue]:
        if isinstance(value, VideoArrayValue):
            return value

        if self._is_fragmented_stream(value):
            async def _iterate():
                async for item in value:
                    video = await self._render_element(item)
                    if video is not None:
                        yield video
            return VideoArrayValue(_iterate())

        if isinstance(value, (list, tuple)):
            return VideoArrayValue([ await self._render_element(item) for item in value ])

        if single_as_array:
            video = await self._render_element(value)
            if video is not None:
                return VideoArrayValue([ video ], is_single=True)

        return None

    async def _render_element(self, value: Any) -> Optional[MediaSource]:
        if value is not None:
            return create_video_source(value)

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
        """True when ``value`` is a list/tuple — a batch of video refs."""
        return isinstance(value, (list, tuple))

    def _is_fragmented_stream(self, value: Any) -> bool:
        """True when ``value`` is a fragmented ``StreamChunkIterator`` — one
        logical video array delivered in pieces.
        """
        return isinstance(value, StreamChunkIterator) and value.is_fragmented
