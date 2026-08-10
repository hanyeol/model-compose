from typing import List, Union, Optional, Any
from collections.abc import AsyncIterator
from ..streaming.iterators import StreamIterator, StreamChunkIterator

class VectorValue:
    def __init__(self, values: List[Union[float, int]]):
        self.values: List[Union[float, int]] = values

class VectorArrayValue:
    def __init__(self, values: List[VectorValue]):
        self.values: List[VectorValue] = values

class VectorValueRenderer:
    async def render_array(
        self,
        value: Any
    ) -> Optional[Union[VectorArrayValue, List[Optional[VectorArrayValue]], AsyncIterator[Optional[VectorArrayValue]]]]:
        if isinstance(value, (StreamIterator, AsyncIterator)):
            async def _iterate():
                async for chunk in value:
                    yield self._render_element_array(chunk)

            # Preserve StreamChunkIterator type for downstream isinstance checks.
            if isinstance(value, StreamChunkIterator):
                return StreamChunkIterator(_iterate(), is_fragmented=value.is_fragmented)

            return _iterate()

        if isinstance(value, (list, tuple)) and value and isinstance(value[0], (list, tuple)) and value[0] and isinstance(value[0][0], (list, tuple)):
            return [ self._render_element_array(item) for item in value ]

        return self._render_element_array(value)

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

    def _render_element_array(self, value: Any) -> Optional[VectorArrayValue]:
        if isinstance(value, VectorArrayValue):
            return value

        if isinstance(value, (list, tuple)):
            return VectorArrayValue([ item for item in (self._render_element(x) for x in value) if item is not None ])

        return None

    def _render_element(self, value: Any) -> Optional[VectorValue]:
        if isinstance(value, VectorValue):
            return value

        if isinstance(value, (list, tuple)):
            return VectorValue(list(value))

        return None
