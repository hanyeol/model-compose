from typing import Union

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

    # Bare numeric strings ("1024", "2048.0") are treated as bytes.
    try:
        return int(float(value))
    except ValueError:
        raise ValueError(f"Unsupported size format: {value}")
