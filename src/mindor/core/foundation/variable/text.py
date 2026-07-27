from typing import Optional, List, Union, Any
from collections.abc import AsyncIterator
from ..streaming.resources import StreamResource
from ..streaming.iterators import StreamIterator, StreamChunkIterator
from ..streaming.text import load_text_from_stream, load_text_from_iterator
from ..streaming.json import encode_value_to_json

class TextValueRenderer:
    async def render(self, value: Any) -> Optional[Union[str, List[Optional[str]], AsyncIterator[Optional[str]]]]:
        # Fragmented streams (e.g. LLM token deltas) represent a single logical
        # text delivered in pieces — fall through to `_render_element` which
        # concatenates them into a complete string.
        is_fragmented_stream = isinstance(value, StreamChunkIterator) and value.is_fragmented

        if isinstance(value, (StreamIterator, AsyncIterator)) and not is_fragmented_stream:
            async def _iterate():
                async for chunk in value:
                    yield await self._render_element(chunk)

            # Non-fragmented case: preserve the StreamChunkIterator type so
            # downstream isinstance checks still recognize it.
            if isinstance(value, StreamChunkIterator):
                return StreamChunkIterator(_iterate(), is_fragmented=value.is_fragmented)

            return _iterate()

        if isinstance(value, (list, tuple)):
            return [ await self._render_element(item) for item in value ]

        return await self._render_element(value)

    async def _render_element(self, value: Any) -> Optional[str]:
        if isinstance(value, str):
            return value

        if isinstance(value, StreamChunkIterator) and value.is_fragmented:
            return await load_text_from_iterator(value)

        if isinstance(value, StreamResource):
            return await load_text_from_stream(value)

        if isinstance(value, (bytes, bytearray)):
            return bytes(value).decode("utf-8", errors="replace")

        if value is not None:
            return await encode_value_to_json(value)

        return None
