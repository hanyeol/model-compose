from typing import List, Union, Optional, Any
from collections.abc import AsyncIterator, AsyncIterable
from ..streaming.iterators import StreamIterator, StreamChunkIterator

class VectorValue:
    def __init__(self, values: List[Union[float, int]]):
        self.values: List[Union[float, int]] = values

class VectorArrayValue:
    """A materialized or streaming array of vectors.

    Backed by either a ``List[VectorValue]`` (re-iterable) or an
    ``AsyncIterable[VectorValue]`` (one-shot). Consumers use ``async for`` to
    iterate lazily, or ``await collect()`` when the full list is needed.
    """
    def __init__(
        self,
        source: Union[List[VectorValue], AsyncIterable[VectorValue]],
        is_single: bool = False,
    ):
        self.source: Union[List[VectorValue], AsyncIterable[VectorValue]] = source
        self.is_single: bool = is_single

    def __aiter__(self) -> AsyncIterator[VectorValue]:
        if isinstance(self.source, list):
            async def _iterate():
                for item in self.source:
                    yield item
            return _iterate()

        return self.source.__aiter__()

    async def collect(self) -> List[VectorValue]:
        if isinstance(self.source, AsyncIterable):
            return [ item async for item in self.source ]

        return self.source

class VectorValueRenderer:
    async def render_array(
        self,
        value: Any,
        item_is_list: bool = False,
        single_as_array: bool = False,
    ) -> Optional[Union[VectorArrayValue, List[Optional[VectorArrayValue]], AsyncIterator[Any]]]:
        """Render a vector array (or a nested list of them, with ``item_is_list=True``).

        Vectors are one axis deeper than scalars: a single element is already
        a 1-D ``List[float]``. The matrix therefore recognises an *explicit
        batch* only when the input is **3-D nested** — a list whose items
        are themselves 2-D vector arrays (or fragmented streams of vectors).
        Under ``item_is_list=True`` the batch axis is always an explicit
        Python list, with non-batch inputs collapsing to a one-element list.
        """
        # Fragmented streams represent one logical vector array delivered in
        # pieces — fall through to ``_render_element_array`` which wraps them
        # into a single streaming VectorArrayValue.
        if isinstance(value, (StreamIterator, AsyncIterator)) and not self._is_fragmented_stream(value):
            async def _iterate():
                async for chunk in value:
                    if item_is_list:
                        yield self._render_element_array(chunk, single_as_array=True)
                    else:
                        yield self._render_element_array(chunk, single_as_array)

            # Preserve StreamChunkIterator type for downstream isinstance checks.
            if isinstance(value, StreamChunkIterator):
                return StreamChunkIterator(_iterate(), is_fragmented=value.is_fragmented)

            return _iterate()

        if item_is_list:
            if self._is_nested_element_array(value):
                return [ self._render_element_array(item, single_as_array=True) for item in value ]

            if single_as_array and value is not None:
                return [ self._render_element_array(value, single_as_array=True) ]

            return None

        if self._is_nested_element_array(value):
            return [ self._render_element_array(item, single_as_array) for item in value ]

        return self._render_element_array(value, single_as_array)

    async def render(
        self,
        value: Any
    ) -> Optional[Union[VectorValue, List[Optional[VectorValue]], AsyncIterator[Optional[VectorValue]]]]:
        if isinstance(value, (StreamIterator, AsyncIterator)):
            async def _iterate():
                async for chunk in value:
                    yield self._render_element(chunk)

            # Preserve StreamChunkIterator type for downstream isinstance checks.
            if isinstance(value, StreamChunkIterator):
                return StreamChunkIterator(_iterate(), is_fragmented=value.is_fragmented)

            return _iterate()

        if isinstance(value, (list, tuple)) and value and isinstance(value[0], (list, tuple)):
            return [ self._render_element(item) for item in value ]

        return self._render_element(value)

    def _render_element_array(self, value: Any, single_as_array: bool = False) -> Optional[VectorArrayValue]:
        if isinstance(value, VectorArrayValue):
            return value

        if self._is_fragmented_stream(value):
            async def _iterate():
                async for item in value:
                    vector = self._render_element(item)
                    if vector is not None:
                        yield vector
            return VectorArrayValue(_iterate())

        # 2-D input or a list of ``VectorValue``s is already batch-shaped.
        if self._is_element_array(value):
            return VectorArrayValue([ vector for vector in (self._render_element(item) for item in value) if vector is not None ])

        # 1-D input (bare vector) is a scalar — only lift under ``single_as_array``.
        if single_as_array:
            vector = self._render_element(value)
            if vector is not None:
                return VectorArrayValue([ vector ], is_single=True)

        return None

    def _render_element(self, value: Any) -> Optional[VectorValue]:
        if isinstance(value, VectorValue):
            return value

        if isinstance(value, (list, tuple)):
            return VectorValue(list(value))

        return None

    def _is_nested_element_array(self, value: Any) -> bool:
        """True when ``value`` is a list of element arrays — a top-level list
        whose first item is itself a batch of vectors (see
        ``_is_element_array``) or a fragmented stream of vectors. Mirrors the
        ``item_is_list=False`` nested check used by other renderers, but
        shifted one axis deeper because a vector is itself a 1-D list.
        """
        return (
            isinstance(value, (list, tuple))
            and bool(value)
            and (self._is_element_array(value[0]) or self._is_fragmented_stream(value[0]))
        )

    def _is_element_array(self, value: Any) -> bool:
        """True when ``value`` is a batch of vectors — a list/tuple whose
        first item is itself a 1-D vector (list, tuple, or ``VectorValue``),
        or an already-materialized ``VectorArrayValue``.
        """
        if isinstance(value, VectorArrayValue):
            return True

        return (
            isinstance(value, (list, tuple))
            and bool(value)
            and isinstance(value[0], (list, tuple, VectorValue))
        )

    def _is_fragmented_stream(self, value: Any) -> bool:
        """True when ``value`` is a fragmented ``StreamChunkIterator`` — one
        logical vector array delivered in pieces.
        """
        return isinstance(value, StreamChunkIterator) and value.is_fragmented
