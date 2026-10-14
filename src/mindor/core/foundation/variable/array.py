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
        item_is_list: bool = False,
        single_as_array: bool = False,
    ) -> Optional[Union[ArrayValue, List[Optional[ArrayValue]], AsyncIterator[Any]]]:
        """Render a generic array (or a nested list of them, with ``item_is_list=True``).

        With ``item_is_list=False`` (default) each ``value`` element is a single
        scalar, and nested lists are interpreted as a batch of arrays.
        With ``item_is_list=True`` each ``value`` element is itself a group of
        scalars; the batch axis is always an explicit Python list, with
        non-batch inputs collapsing to a one-element list.
        """
        # Fragmented streams represent a single logical array delivered as an
        # element stream — fall through to ``_render_element`` which wraps
        # them into one streaming ArrayValue.
        if isinstance(value, (StreamIterator, AsyncIterator)) and not self._is_fragmented_stream(value):
            async def _iterate():
                async for chunk in value:
                    if item_is_list:
                        yield self._render_element(chunk, single_as_array=True)
                    else:
                        yield self._render_element(chunk, single_as_array)

            # Preserve StreamChunkIterator type for downstream isinstance checks.
            if isinstance(value, StreamChunkIterator):
                return StreamChunkIterator(_iterate(), is_fragmented=value.is_fragmented)

            return _iterate()

        if item_is_list:
            if self._is_nested_element(value):
                return [ self._render_element(item, single_as_array=True) for item in value ]

            if single_as_array and value is not None:
                return [ self._render_element(value, single_as_array=True) ]

            return None

        if self._is_nested_element(value):
            return [ self._render_element(item, single_as_array) for item in value ]

        return self._render_element(value, single_as_array)

    def _render_element(self, value: Any, single_as_array: bool = False) -> Optional[ArrayValue]:
        if isinstance(value, ArrayValue):
            return value

        if self._is_fragmented_stream(value):
            async def _iterate():
                async for item in value:
                    if item is not None:
                        yield item
            return ArrayValue(_iterate())

        if isinstance(value, (list, tuple)):
            return ArrayValue(list(value))

        if single_as_array and value is not None:
            return ArrayValue([ value ], is_single=True)

        if value is not None:
            raise TypeError(
                f"expected an array (list, ArrayValue, or fragmented stream) "
                f"but got a single value. Join a per-item stream with \"+\"."
            )

        return None

    def _is_nested_element(self, value: Any) -> bool:
        """True when ``value`` is a list of element arrays — a top-level
        list whose first item is itself an element array or a fragmented
        stream.
        """
        return (
            isinstance(value, (list, tuple))
            and bool(value)
            and (self._is_element(value[0]) or self._is_fragmented_stream(value[0]))
        )

    def _is_element(self, value: Any) -> bool:
        """True when ``value`` is a list/tuple or an already-materialized
        ``ArrayValue`` — one element (= array).
        """
        return isinstance(value, (list, tuple, ArrayValue))

    def _is_fragmented_stream(self, value: Any) -> bool:
        """True when ``value`` is a fragmented ``StreamChunkIterator`` — one
        logical array delivered in pieces.
        """
        return isinstance(value, StreamChunkIterator) and value.is_fragmented
