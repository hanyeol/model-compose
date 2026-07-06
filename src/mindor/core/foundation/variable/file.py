from typing import Optional, List, Union, Any
from collections.abc import AsyncIterator
from ..streaming.resources import StreamResource, save_stream_to_temporary_file
from ..streaming.file import FileStreamResource
from ..streaming.iterators import StreamIterator

class FileValueRenderer:
    async def render(self, value: Any) -> Optional[Union[str, List[Optional[str]], AsyncIterator[Optional[str]]]]:
        if isinstance(value, (StreamIterator, AsyncIterator)):
            async def _iterate():
                async for chunk in value:
                    yield await self._render_element(chunk)
            return _iterate()

        if isinstance(value, (list, tuple)):
            return [ await self._render_element(item) for item in value ]

        return await self._render_element(value)

    async def _render_element(self, value: Any) -> Optional[str]:
        if isinstance(value, FileStreamResource):
            return value.path

        if isinstance(value, StreamResource):
            return await save_stream_to_temporary_file(value, None)

        return None
