from typing import Optional, List, Union, Any
from collections.abc import AsyncIterator
from ..streaming.resources import StreamResource
from ..streaming.iterators import StreamIterator, StreamChunkIterator
from ..streaming.text import TextStreamResource, load_text_from_stream, load_text_from_iterator
from ..streaming.json import encode_value_to_json

class TextValueRenderer:
    async def render(
        self,
        value: Any,
        collect: bool = True,
    ) -> Optional[Union[str, List[Optional[str]], StreamChunkIterator, AsyncIterator[Optional[str]]]]:
        # ``collect`` controls how fragmented streams (a single logical text
        # delivered in pieces) are handled:
        # - True  (default): concatenate the pieces into a complete ``str``.
        #   This is what most callers want (LLM prompts, embedding inputs,
        #   URLs, HTML templates, ...).
        # - False: pass the ``StreamChunkIterator(is_fragmented=True)`` through
        #   unchanged so streaming consumers (splitters, transcript aligner)
        #   can feed pieces incrementally instead of blocking on the full text.
        is_fragmented_stream = isinstance(value, StreamChunkIterator) and value.is_fragmented

        if isinstance(value, (StreamIterator, AsyncIterator)) and not is_fragmented_stream:
            async def _iterate():
                async for chunk in value:
                    yield await self._render_element(chunk, collect=collect)

            # Non-fragmented case: preserve the StreamChunkIterator type so
            # downstream isinstance checks still recognize it.
            if isinstance(value, StreamChunkIterator):
                return StreamChunkIterator(_iterate(), is_fragmented=False)

            return _iterate()

        if isinstance(value, (list, tuple)):
            return [ await self._render_element(item, collect=collect) for item in value ]

        return await self._render_element(value, collect=collect)

    async def _render_element(self, value: Any, collect: bool = True) -> Any:
        if isinstance(value, str):
            return value

        if isinstance(value, TextStreamResource):
            return value.text

        if isinstance(value, StreamChunkIterator) and value.is_fragmented:
            if collect:
                return await load_text_from_iterator(value)
            return value

        if isinstance(value, StreamResource):
            return await load_text_from_stream(value)

        if isinstance(value, (bytes, bytearray)):
            return bytes(value).decode("utf-8", errors="replace")

        if value is not None:
            return await encode_value_to_json(value)

        return None
