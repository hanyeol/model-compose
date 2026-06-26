from typing import List, Union, Any
from collections.abc import AsyncIterator
from ..streaming.audio import create_audio_source
from ..streaming.media import MediaSource

class AudioValueRenderer:
    async def render(self, value: Any) -> Union[MediaSource, List[MediaSource], AsyncIterator[MediaSource]]:
        if isinstance(value, AsyncIterator):
            async def _iterate():
                async for element in value:
                    yield await self._render_element(element)
            return _iterate()

        if isinstance(value, (list, tuple)):
            return [ await self._render_element(element) for element in value ]

        return await self._render_element(value)

    async def _render_element(self, element: Any) -> MediaSource:
        return create_audio_source(element)
