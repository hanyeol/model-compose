from typing import Any
from enum import Enum

class EnumToStrConverter:
    def convert(self, value: Any) -> Any:
        return self._convert_element(value)

    def _convert_element(self, element: Any) -> Any:
        if isinstance(element, Enum):
            return element.value
        
        if isinstance(element, dict):
            return { key: self._convert_element(value) for key, value in element.items() }
        
        if isinstance(element, list):
            return [ self._convert_element(item) for item in element ]

        if isinstance(element, tuple):
            return tuple(self._convert_element(item) for item in element)

        if isinstance(element, set):
            return { self._convert_element(item) for item in element }

        return element

def enum_union_to_str(value: Any) -> Any:
    return EnumToStrConverter().convert(value)
