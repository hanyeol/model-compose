from typing import List, Optional, Union, Any
from collections.abc import AsyncIterator
from ..streaming.media import MediaSource, create_media_source
from ..streaming.iterators import StreamIterator

class MediaValueRenderer:
    async def render(self, value: Any) -> Optional[Union[MediaSource, List[Optional[MediaSource]], AsyncIterator[Optional[MediaSource]]]]:
        if isinstance(value, (StreamIterator, AsyncIterator)):
            async def _iterate():
                async for chunk in value:
                    yield await self._render_element(chunk)
            return _iterate()

        if isinstance(value, (list, tuple)):
            return [ await self._render_element(item) for item in value ]

        return await self._render_element(value)

    async def _render_element(self, value: Any) -> Optional[MediaSource]:
        if value is not None:
            return create_media_source(value)
        return None
