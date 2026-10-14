from typing import Optional, List, Union, Any
from collections.abc import AsyncIterator, AsyncIterable
from ..streaming.resources import StreamResource
from ..streaming.iterators import StreamIterator, StreamChunkIterator
from ..streaming.text import TextStreamResource, load_text_from_stream, load_text_from_iterator
from ..streaming.json import encode_value_to_json
TextValue = str

class TextArrayValue:
    """A materialized or streaming array of texts.

    Mirrors ImageArrayValue — elements are already normalized to ``str`` before
    they reach this container. ``is_single`` is set when a single input was
    coerced into a one-element array via ``single_as_array=True``.
    """
    def __init__(
        self,
        source: Union[List[TextValue], AsyncIterable[TextValue]],
        is_single: bool = False,
    ):
        self.source: Union[List[TextValue], AsyncIterable[TextValue]] = source
        self.is_single: bool = is_single

    def __aiter__(self) -> AsyncIterator[TextValue]:
        if isinstance(self.source, list):
            async def _iterate():
                for item in self.source:
                    yield item
            return _iterate()

        return self.source.__aiter__()

    async def collect(self) -> List[TextValue]:
        if isinstance(self.source, AsyncIterable):
            return [ item async for item in self.source ]

        return self.source

class TextValueRenderer:
    async def render_array(
        self,
        value: Any,
        item_is_list: bool = False,
        single_as_array: bool = False,
    ) -> Optional[Union[TextArrayValue, List[Optional[TextArrayValue]], AsyncIterator[Any]]]:
        """Render a text array (or a nested list of them, with ``item_is_list=True``).

        With ``item_is_list=False`` (default) each ``value`` element is a single
        text, and nested lists are interpreted as a batch of text arrays.
        With ``item_is_list=True`` each ``value`` element is itself a group of
        text refs; the batch axis is always an explicit Python list, with
        non-batch inputs collapsing to a one-element list.
        """
        # Fragmented streams represent a single logical text array delivered in
        # pieces — fall through to `_render_element_array` which wraps them into
        # one streaming TextArrayValue.
        if isinstance(value, (StreamIterator, AsyncIterator)) and not self._is_fragmented_stream(value):
            async def _iterate():
                async for chunk in value:
                    if item_is_list:
                        yield await self._render_element_array(chunk, single_as_array=True)
                    else:
                        yield await self._render_element_array(chunk, single_as_array)

            # Preserve StreamChunkIterator type for downstream isinstance checks.
            if isinstance(value, StreamChunkIterator):
                return StreamChunkIterator(_iterate(), is_fragmented=value.is_fragmented)

            return _iterate()

        if item_is_list:
            if self._is_nested_element_array(value):
                return [ await self._render_element_array(item, single_as_array=True) for item in value ]

            if single_as_array and value is not None:
                return [ await self._render_element_array(value, single_as_array=True) ]

            return None

        if self._is_nested_element_array(value):
            return [ await self._render_element_array(item, single_as_array) for item in value ]

        return await self._render_element_array(value, single_as_array)

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
        if isinstance(value, (StreamIterator, AsyncIterator)) and not self._is_fragmented_stream(value):
            async def _iterate():
                async for chunk in value:
                    yield await self._render_element(chunk, collect=collect)

            # Preserve StreamChunkIterator type for downstream isinstance checks.
            if isinstance(value, StreamChunkIterator):
                return StreamChunkIterator(_iterate(), is_fragmented=False)

            return _iterate()

        if isinstance(value, (list, tuple)):
            return [ await self._render_element(item, collect=collect) for item in value ]

        return await self._render_element(value, collect=collect)

    async def _render_element_array(
        self,
        value: Any,
        single_as_array: bool = False,
    ) -> Optional[TextArrayValue]:
        if isinstance(value, TextArrayValue):
            async def _iterate():
                async for item in value:
                    text = await self._render_element(item, collect=True)
                    if text is not None:
                        yield text
            return TextArrayValue(_iterate(), is_single=value.is_single)

        if self._is_fragmented_stream(value):
            async def _iterate():
                async for item in value:
                    text = await self._render_element(item, collect=True)
                    if text is not None:
                        yield text
            return TextArrayValue(_iterate())

        if isinstance(value, (list, tuple)):
            return TextArrayValue([ await self._render_element(item, collect=True) for item in value ])

        if single_as_array and value is not None:
            text = await self._render_element(value, collect=True)
            if text is not None:
                return TextArrayValue([ text ], is_single=True)

        if value is not None:
            raise TypeError(
                f"expected a text array (list, TextArrayValue, or fragmented stream) "
                f"but got a single text. Join a per-item stream with \"+\"."
            )

        return None

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

    def _is_nested_element_array(self, value: Any) -> bool:
        """True when ``value`` is a list of element arrays — a top-level
        list whose first item is itself an element array or a fragmented
        stream.
        """
        return (
            isinstance(value, (list, tuple))
            and bool(value)
            and (self._is_element_array(value[0]) or self._is_fragmented_stream(value[0]))
        )

    def _is_element_array(self, value: Any) -> bool:
        """True when ``value`` is a batch of text refs — a list/tuple of
        refs or an already-materialized ``TextArrayValue``.
        """
        return isinstance(value, (list, tuple, TextArrayValue))

    def _is_fragmented_stream(self, value: Any) -> bool:
        """True when ``value`` is a fragmented ``StreamChunkIterator`` — one
        logical text array delivered in pieces.
        """
        return isinstance(value, StreamChunkIterator) and value.is_fragmented
