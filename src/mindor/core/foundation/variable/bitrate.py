from typing import Union

def parse_bitrate(value: Union[str, int, float]) -> int:
    """Parse a bitrate string like '2M' or '128k' into bits per second.

    Uses SI (decimal) units per the bitrate convention: 1k = 1000, 1M = 1_000_000.
    """
    if isinstance(value, (float, int)):
        return int(value)

    if value.endswith("G") or value.endswith("g"):
        return int(float(value[:-1]) * 1_000_000_000)

    if value.endswith("M") or value.endswith("m"):
        return int(float(value[:-1]) * 1_000_000)

    if value.endswith("K") or value.endswith("k"):
        return int(float(value[:-1]) * 1_000)

    raise ValueError(f"Unsupported bitrate format: {value}")
