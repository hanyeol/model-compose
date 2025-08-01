from typing import Dict, List, Any
import re

class FieldResolver:
    def __init__(self):
        self.patterns: Dict[str, re.Pattern] = {
            "keypath": re.compile(r"[-_\w]+|\[\d+\]"),
        }

    def resolve(self, object: dict, path: str, default: Any = None) -> Any:
        parts: List[str] = self.patterns["keypath"].findall(path) if path else []
        current = object

        for part in parts:
            if isinstance(current, dict) and not part.startswith("["):
                if part in current:
                    current = current[part]
                else:
                    return default
            elif isinstance(current, list) and part.startswith("["):
                index = int(part[1:-1])
                if 0 <= index < len(current):
                    current = current[index]
                else:
                    return default
            else:
                return default
        
        return current
