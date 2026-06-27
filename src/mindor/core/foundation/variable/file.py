from typing import Optional, List, Union, Any
from collections.abc import AsyncIterator
from ..streaming.resources import StreamResource, save_stream_to_temporary_file
from ..streaming.file import FileStreamResource

class FileValueRenderer:
    async def render(self, value: Any) -> Optional[Union[str, List[Optional[str]], AsyncIterator[Optional[str]]]]:
        if isinstance(value, AsyncIterator):
            async def _iterate():
                async for element in value:
                    yield await self._render_element(element)
            return _iterate()

        if isinstance(value, (list, tuple)):
            return [ await self._render_element(element) for element in value ]

        return await self._render_element(value)

    async def _render_element(self, value: Any) -> Optional[str]:
        if isinstance(value, FileStreamResource):
            return value.path

        if isinstance(value, StreamResource):
            return await save_stream_to_temporary_file(value, None)

        return None
