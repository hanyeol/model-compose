from typing import Optional, List, Union, Any
from collections.abc import AsyncIterator
from ..streaming.resources import StreamResource
from ..streaming.text import load_text_from_stream
import json

class TextValueRenderer:
    async def render(self, value: Any) -> Optional[Union[str, List[Optional[str]], AsyncIterator[Optional[str]]]]:
        if isinstance(value, AsyncIterator):
            async def _iterate():
                async for chunk in value:
                    yield await self._render_element(chunk)
            return _iterate()

        if isinstance(value, (list, tuple)):
            return [ await self._render_element(item) for item in value ]

        return await self._render_element(value)

    async def _render_element(self, value: Any) -> Optional[str]:
        if isinstance(value, str):
            return value

        if isinstance(value, StreamResource):
            return await load_text_from_stream(value)

        if isinstance(value, (bytes, bytearray)):
            return bytes(value).decode("utf-8", errors="replace")

        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, default=str)

        return str(value) if value is not None else None
