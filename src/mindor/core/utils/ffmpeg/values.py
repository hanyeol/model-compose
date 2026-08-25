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

def parse_duration(value: Optional[str]) -> Optional[float]:
    """Parse an `HH:MM:SS(.ms)` timestamp into seconds."""
    match = re.fullmatch(r"(\d+):(\d+):(\d+(?:\.\d+)?)", value) if value else None

    if not match:
        return None

    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)

def read_duration(text: str, label: str) -> Optional[float]:
    """Read a labeled `HH:MM:SS(.ms)` timestamp from ffmpeg text output.

    ffmpeg's stderr header uses the `Duration` label for the source's declared
    duration (not the amount actually decoded); other filters may print their
    own labeled timestamps in the same format.
    """
    match = re.search(rf"{re.escape(label)}:\s*(\d+:\d+:\d+(?:\.\d+)?)", text)

    if match:
        return parse_duration(match.group(1))

    return None
