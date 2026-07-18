from __future__ import annotations

from typing import Any, Type, TypeVar
from enum import Enum

_E = TypeVar("_E", bound=Enum)

def coerce_enum(value: Any, enum_cls: Type[_E], field: str) -> _E:
    """Normalize a value into an enum member.

    A rendered variable may return either the enum instance (when the config
    literal was preserved) or a raw string (when the value came from
    interpolation such as `${input.audio_source}`).
    """
    if not isinstance(value, enum_cls):
        try:
            return enum_cls(value)
        except (ValueError, TypeError):
            allowed = ", ".join(member.value for member in enum_cls)
            raise ValueError(f"invalid {field!r}: {value!r} (allowed: {allowed})")
    
    return value
