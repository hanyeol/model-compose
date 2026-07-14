from typing import List, Union, Any
from collections.abc import AsyncIterator
from ..streaming.iterators import StreamIterator

class VectorValue:
    def __init__(self, values: List[Union[float, int]]):
        self.values: List[Union[float, int]] = values

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

    async def render_list(self, value: Any) -> Union[List[VectorValue], AsyncIterator[List[VectorValue]]]:
        if isinstance(value, (StreamIterator, AsyncIterator)):
            async def _iterate():
                async for chunk in value:
                    yield self._render_element_list(chunk)
            return _iterate()

        return self._render_element_list(value)

    def _render_element_list(self, value: Any) -> List[VectorValue]:
        if isinstance(value, (list, tuple)):
            if not value:
                return []
            if isinstance(value[0], (list, tuple)):
                return [ self._render_element(item) for item in value ]
            return [ self._render_element(value) ]

        return [ self._render_element(value) ]

    def _render_element(self, value: Any) -> VectorValue:
        if isinstance(value, VectorValue):
            return value

        if isinstance(value, (list, tuple)):
            return VectorValue(list(value))

        raise TypeError(f"Cannot render element of type {type(value).__name__} as vector")
