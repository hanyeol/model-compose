from __future__ import annotations

from typing import Optional
import re

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

def read_float(text: str, label: str) -> Optional[float]:
    """Read a labeled float value from ffmpeg text output.

    Matches `<label>: <value>` where the value can be a decimal number or one
    of ffmpeg's `inf` / `-inf` / `nan` sentinels; the latter are surfaced as
    None via `parse_float`.
    """
    match = re.search(rf"{re.escape(label)}:\s*(-?\d+(?:\.\d+)?|inf|-inf|nan)", text)

    if match:
        return parse_float(match.group(1))

    return None

def read_int(text: str, label: str) -> Optional[int]:
    """Read a labeled integer value from ffmpeg text output."""
    match = re.search(rf"{re.escape(label)}:\s*(\d+)", text)

    if match:
        return int(match.group(1))

    return None
