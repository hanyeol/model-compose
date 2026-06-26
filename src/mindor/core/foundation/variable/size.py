from typing import Optional, Union, Any

class SizeValueRenderer:
    async def render(self, value: Any, default: Optional[int] = None) -> Optional[int]:
        if isinstance(value, (str, int, float)):
            return parse_size(value)

        return default

def parse_size(value: Union[str, int, float]) -> int:
    if isinstance(value, (float, int)):
        return int(value)

    if value.endswith("GB"):
        return int(float(value[:-2]) * 1024 ** 3)

    if value.endswith("MB"):
        return int(float(value[:-2]) * 1024 ** 2)

    if value.endswith("KB"):
        return int(float(value[:-2]) * 1024)

    if value.endswith("G"):
        return int(float(value[:-1]) * 1024 ** 3)

    if value.endswith("M"):
        return int(float(value[:-1]) * 1024 ** 2)

    if value.endswith("K"):
        return int(float(value[:-1]) * 1024)

    if value.endswith("B"):
        return int(float(value[:-1]))

    raise ValueError(f"Unsupported size format: {value}")
