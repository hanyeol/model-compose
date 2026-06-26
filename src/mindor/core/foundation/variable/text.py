from typing import Optional, List, Union, Any
from collections.abc import AsyncIterator
from ..streaming.resources import StreamResource
from ..streaming.text import load_text_from_stream
import json

class TextValueRenderer:
    async def render(self, value: Any) -> Optional[Union[str, List[Optional[str]], AsyncIterator[Optional[str]]]]:
        if isinstance(value, AsyncIterator):
            async def _iterate():
                async for element in value:
                    yield await self._render_element(element)
            return _iterate()

        if isinstance(value, (list, tuple)):
            return [ await self._render_element(element) for element in value ]

        return await self._render_element(value)

    async def _render_element(self, element: Any) -> Optional[str]:
        if isinstance(element, str):
            return element

        if isinstance(element, StreamResource):
            return await load_text_from_stream(element)

        if isinstance(element, (bytes, bytearray)):
            return bytes(element).decode("utf-8", errors="replace")

        if isinstance(element, (dict, list)):
            return json.dumps(element, ensure_ascii=False, default=str)

        return str(element) if element is not None else None
