from typing import Optional, List, Union, Any
from collections.abc import AsyncIterator

class ArrayValue:
    def __init__(self, values: List[Any]):
        self.values: List[Any] = values

class ArrayValueRenderer:
    async def render(self, value: Any) -> Optional[Union[ArrayValue, List[Optional[ArrayValue]], AsyncIterator[Optional[ArrayValue]]]]:
        if isinstance(value, AsyncIterator):
            async def _iterate():
                async for element in value:
                    yield self._render_element(element)
            return _iterate()

        if isinstance(value, list) and value and isinstance(value[0], list):
            return [ self._render_element(element) for element in value ]

        return self._render_element(value)

    def _render_element(self, element: Any) -> Optional[ArrayValue]:
        if isinstance(element, ArrayValue):
            return element

        if isinstance(element, (list, tuple)):
            return ArrayValue(list(element))

        return None
