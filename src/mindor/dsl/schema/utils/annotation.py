from typing import Set, Any, get_args
from pydantic import BaseModel

def get_model_union_keys(model_union_type: Any) -> Set[str]:
    keys, stack = set(), [ model_union_type ]

    while stack:
        current = stack.pop()
         
        if isinstance(current, type) and issubclass(current, BaseModel):
            keys |= set(current.model_fields.keys())
            continue

        args = get_args(current)
        if args:
            stack.extend(args)
            continue

    return keys
