from typing import List, Union, Any
from collections.abc import AsyncIterator
from ..streaming.media import MediaSource, create_media_source

class MediaValueRenderer:
    async def render(self, value: Any) -> Union[MediaSource, List[MediaSource], AsyncIterator[MediaSource]]:
        if isinstance(value, AsyncIterator):
            async def _iterate():
                async for element in value:
                    yield await self._render_element(element)
            return _iterate()

        if isinstance(value, (list, tuple)):
            return [ await self._render_element(element) for element in value ]

        return await self._render_element(value)

    async def _render_element(self, value: Any) -> MediaSource:
        return create_media_source(value)
