from typing import List, Optional, Union, Any
from collections.abc import AsyncIterator, AsyncIterable
from ..streaming.video import create_video_source
from ..streaming.media import MediaSource
from ..streaming.iterators import StreamIterator, StreamChunkIterator

class VideoArrayValue:
    """A materialized or streaming array of video sources.

    Backed by either a `List[MediaSource]` (re-iterable) or an
    `AsyncIterable[MediaSource]` (one-shot). Consumers use `async for` to
    iterate lazily, or `await collect()` when the full list is needed.
    """
    def __init__(self, source: Union[List[MediaSource], AsyncIterable[MediaSource]]):
        self.source: Union[List[MediaSource], AsyncIterable[MediaSource]] = source

    def __aiter__(self) -> AsyncIterator[MediaSource]:
        if isinstance(self.source, list):
            async def _iterate():
                for item in self.source:
                    yield item
            return _iterate()

        return self.source.__aiter__()

    async def collect(self) -> List[MediaSource]:
        if isinstance(self.source, list):
            return self.source

        return [ item async for item in self.source ]

class VideoValueRenderer:
    async def render_array(
        self,
        value: Any
    ) -> Optional[Union[VideoArrayValue, List[Optional[VideoArrayValue]], AsyncIterator[Optional[VideoArrayValue]]]]:
        # Fragmented streams represent a single logical video array delivered
        # in pieces — fall through to `_render_element_array` which wraps them
        # into one streaming VideoArrayValue.
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

    async def _render_element_array(self, value: Any) -> Optional[VideoArrayValue]:
        if isinstance(value, VideoArrayValue):
            return value

        if isinstance(value, StreamChunkIterator) and value.is_fragmented:
            async def _iterate():
                async for item in value:
                    video = await self._render_element(item)
                    if video is not None:
                        yield video
            return VideoArrayValue(_iterate())

        if isinstance(value, (list, tuple)):
            return VideoArrayValue([ await self._render_element(item) for item in value if item is not None ])

        return None

    async def _render_element(self, value: Any) -> Optional[MediaSource]:
        if value is not None:
            return create_video_source(value)

        return None
