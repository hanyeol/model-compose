from typing import Dict, List, Optional, Any
import re

class FieldResolver:
    def __init__(self):
        self.patterns: Dict[str, re.Pattern] = {
            "keypath": re.compile(r"[-_\w]+|\[-?\d+\]|\[\*\]"),
        }

    def resolve(self, object: Any, path: Optional[str], default: Any = None) -> Any:
        if path is not None:
            return self._resolve_value(object, self.patterns["keypath"].findall(path), default)

        return object

    def _resolve_value(self, object: Any, segments: List[str], default: Any) -> Any:
        value = object
        for index, segment in enumerate(segments):
            if segment == "[*]":
                if not isinstance(value, list):
                    return default
                return [ self._resolve_value(item, segments[index + 1:], default) for item in value ]

            if segment.startswith("["):
                if not isinstance(value, list):
                    return default
                i = int(segment[1:-1])
                if not -len(value) <= i < len(value):
                    return default
                value = value[i]
            else:
                if not isinstance(value, dict):
                    return default
                if segment not in value:
                    return default
                value = value[segment]

        return value
