from typing import List, Union, Any
from collections.abc import AsyncIterator
from ..streaming.video import create_video_source
from ..streaming.media import MediaSource
from ..streaming.iterators import StreamIterator

class VideoValueRenderer:
    async def render(self, value: Any) -> Union[MediaSource, List[MediaSource], AsyncIterator[MediaSource]]:
        if isinstance(value, (StreamIterator, AsyncIterator)):
            async def _iterate():
                async for chunk in value:
                    yield await self._render_element(chunk)
            return _iterate()

        if isinstance(value, (list, tuple)):
            return [ await self._render_element(item) for item in value ]

        return await self._render_element(value)

    async def _render_element(self, value: Any) -> MediaSource:
        return create_video_source(value)
