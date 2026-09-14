from typing import Tuple, Union, Optional, List

Box = Tuple[Optional[int], Optional[int], Optional[int], Optional[int]]

def parse_box(value: Union[list, tuple]) -> Box:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"Unsupported box value: {value!r}")

    if len(value) != 4:
        raise ValueError(f"Box must have 4 elements (left, top, right, bottom): {value!r}")

    return tuple(None if element is None else int(element) for element in value)
