from typing import List, Union, Optional, Any
from collections.abc import AsyncIterator, AsyncIterable
from ..streaming.iterators import StreamIterator, StreamChunkIterator

class ArrayValue:
    """A materialized or streaming array of arbitrary elements.

    Backed by either a ``List[Any]`` (re-iterable) or an
    ``AsyncIterable[Any]`` (one-shot). Consumers use ``async for`` to iterate
    lazily, or ``await collect()`` when the full list is needed.
    """
    def __init__(self, source: Union[List[Any], AsyncIterable[Any]], is_single: bool = False):
        self.source: Union[List[Any], AsyncIterable[Any]] = source
        self.is_single: bool = is_single

    def __aiter__(self) -> AsyncIterator[Any]:
        if isinstance(self.source, list):
            async def _iterate():
                for item in self.source:
                    yield item
            return _iterate()

        return self.source.__aiter__()

    async def collect(self) -> List[Any]:
        if isinstance(self.source, AsyncIterable):
            return [ item async for item in self.source ]

        return self.source

class ArrayValueRenderer:
    async def render(
        self,
        value: Any,
        single_as_array: bool = False,
    ) -> Optional[Union[ArrayValue, List[Optional[ArrayValue]], AsyncIterator[Optional[ArrayValue]]]]:
        # Fragmented streams represent a single logical array delivered as an
        # element stream — fall through to ``_render_element`` which wraps
        # them into one streaming ArrayValue.
        is_fragmented_stream = isinstance(value, StreamChunkIterator) and value.is_fragmented

        if isinstance(value, (StreamIterator, AsyncIterator)) and not is_fragmented_stream:
            async def _iterate():
                async for chunk in value:
                    yield self._render_element(chunk, single_as_array)

            # Preserve StreamChunkIterator type for downstream isinstance checks.
            if isinstance(value, StreamChunkIterator):
                return StreamChunkIterator(_iterate(), is_fragmented=value.is_fragmented)

            return _iterate()

        if isinstance(value, (list, tuple)) and value and isinstance(value[0], (list, tuple, StreamChunkIterator)):
            return [ self._render_element(item, single_as_array) for item in value ]

        return self._render_element(value, single_as_array)

    def _render_element(self, value: Any, single_as_array: bool = False) -> Optional[ArrayValue]:
        if isinstance(value, ArrayValue):
            return value

        if isinstance(value, StreamChunkIterator) and value.is_fragmented:
            async def _iterate():
                async for item in value:
                    if item is not None:
                        yield item
            return ArrayValue(_iterate())

        if isinstance(value, (StreamIterator, AsyncIterator)):
            # Bare async iterator whose elements are the array's elements — wrap
            # unchanged so ArrayValue delivers them lazily.
            return ArrayValue(value)

        if isinstance(value, (list, tuple)):
            return ArrayValue(list(value))

        if single_as_array and value is not None:
            return ArrayValue([ value ], is_single=True)

        return None
