from typing import List, Union, Any
from collections.abc import AsyncIterator
from ..streaming.iterators import StreamIterator

class VectorValue:
    def __init__(self, values: List[Union[float, int]]):
        self.values: List[Union[float, int]] = values

class VectorArrayValue:
    def __init__(self, values: List[VectorValue]):
        self.values: List[VectorValue] = values

class VectorValueRenderer:
    async def render(self, value: Any) -> Union[VectorValue, List[VectorValue], AsyncIterator[VectorValue]]:
        if isinstance(value, (StreamIterator, AsyncIterator)):
            async def _iterate():
                async for chunk in value:
                    yield self._render_element(chunk)
            return _iterate()

        if isinstance(value, (list, tuple)) and value and isinstance(value[0], (list, tuple)):
            return [ self._render_element(item) for item in value ]

        return self._render_element(value)

    async def render_array(self, value: Any) -> Union[VectorArrayValue, List[VectorArrayValue], AsyncIterator[VectorArrayValue]]:
        if isinstance(value, (StreamIterator, AsyncIterator)):
            async def _iterate():
                async for chunk in value:
                    yield self._render_element_array(chunk)
            return _iterate()

        if isinstance(value, (list, tuple)) and value and isinstance(value[0], (list, tuple)) and value[0] and isinstance(value[0][0], (list, tuple)):
            return [ self._render_element_array(item) for item in value ]

        return self._render_element_array(value)

    def _render_element_array(self, value: Any) -> VectorArrayValue:
        if isinstance(value, VectorArrayValue):
            return value

        if isinstance(value, (list, tuple)):
            return VectorArrayValue([ self._render_element(item) for item in value ])

        raise TypeError(f"Cannot render element of type {type(value).__name__} as vector array")

    def _render_element(self, value: Any) -> VectorValue:
        if isinstance(value, VectorValue):
            return value

        if isinstance(value, (list, tuple)):
            return VectorValue(list(value))

        raise TypeError(f"Cannot render element of type {type(value).__name__} as vector")
