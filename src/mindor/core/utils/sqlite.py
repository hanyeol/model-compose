from typing import Any

def escape_fts_term(value: Any) -> str:
    return '"' + str(value).replace('"', '""') + '"'
