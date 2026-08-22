from typing import Any
import json, re

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

def validate_identifier(name: str, kind: str = "identifier") -> str:
    if not isinstance(name, str) or not _IDENTIFIER_RE.match(name):
        raise ValueError(f"Invalid {kind} name: {name!r}. Must match [A-Za-z_][A-Za-z0-9_]*.")

    return name

def quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'

def serialize_value(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, str):
        return value

    if isinstance(value, bool):
        return "true" if value else "false"

    if isinstance(value, (int, float)):
        return str(value)

    return json.dumps(value, ensure_ascii=False)
