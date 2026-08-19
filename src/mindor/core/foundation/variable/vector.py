from typing import List, Union, Optional, Any
from collections.abc import AsyncIterator
from ..streaming.iterators import StreamIterator, StreamChunkIterator

class VectorValue:
    def __init__(self, values: List[Union[float, int]]):
        self.values: List[Union[float, int]] = values

class VectorArrayValue:
    def __init__(self, values: List[VectorValue], is_single: bool = False):
        self.values: List[VectorValue] = values
        self.is_single: bool = is_single

    def __aiter__(self) -> AsyncIterator[VectorValue]:
        async def _iterate():
            for value in self.values:
                yield value
        return _iterate()

    async def collect(self) -> List[List[Union[float, int]]]:
        return [ vector.values for vector in self.values ]

class VectorValueRenderer:
    async def render_array(
        self,
        value: Any,
        single_as_array: bool = False,
    ) -> Optional[Union[VectorArrayValue, List[Optional[VectorArrayValue]], AsyncIterator[Optional[VectorArrayValue]]]]:
        if isinstance(value, (StreamIterator, AsyncIterator)):
            async def _iterate():
                async for chunk in value:
                    yield self._render_element_array(chunk, single_as_array)

            # Preserve StreamChunkIterator type for downstream isinstance checks.
            if isinstance(value, StreamChunkIterator):
                return StreamChunkIterator(_iterate(), is_fragmented=value.is_fragmented)

            return _iterate()

        if isinstance(value, (list, tuple)) and value and isinstance(value[0], (list, tuple)) and value[0] and isinstance(value[0][0], (list, tuple)):
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

        if isinstance(value, (list, tuple)) and value and isinstance(value[0], (list, tuple, VectorValue)):
            return VectorArrayValue([ vector for vector in (self._render_element(item) for item in value) if vector is not None ])

        # Wrap a bare vector (list of floats) as a one-element VectorArrayValue so
        # single-vector inputs match the batch shape callers expect.
        if single_as_array and isinstance(value, (list, tuple)):
            return VectorArrayValue([ VectorValue(list(value)) ], is_single=True)

        return None

    def _render_element(self, value: Any) -> Optional[VectorValue]:
        if isinstance(value, VectorValue):
            return value

        if isinstance(value, (list, tuple)):
            return VectorValue(list(value))

        return None
