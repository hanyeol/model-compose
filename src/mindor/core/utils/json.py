from typing import Any

_JSON_SCALAR_TYPES = (str, int, float, bool, type(None))

def to_json_safe(value: Any) -> Any:
    """Best-effort conversion of arbitrary values into JSON-safe form.

    Payloads carried across IPC or serialized for logging may contain raw
    domain objects (e.g. `PcmStreamResource`) that cannot be JSON-encoded.
    Scalars pass through, dict/list/tuple recurse, and anything else falls
    back to `repr()` so consumers still see something informative.
    """
    if isinstance(value, _JSON_SCALAR_TYPES):
        return value
    if isinstance(value, dict):
        return { str(key): to_json_safe(item) for key, item in value.items() }
    if isinstance(value, (list, tuple)):
        return [ to_json_safe(item) for item in value ]
    return repr(value)
