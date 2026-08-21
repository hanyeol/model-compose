from __future__ import annotations

from typing import Optional

def parse_float(value: Optional[str]) -> Optional[float]:
    """Parse a float from ffmpeg text output, returning None for its sentinels.

    Filters like `astats` and `ebur128` emit `inf`, `-inf`, and `nan` when a
    measurement is undefined (e.g. silent input yields `-inf dBFS`). Callers
    typically want those surfaced as missing values rather than floats that
    poison downstream arithmetic.
    """
    if value in ("inf", "-inf", "nan"):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None
