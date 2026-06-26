from typing import Union
from datetime import datetime, timezone
from enum import Enum

class TimezoneFormat(str, Enum):
    ZULU   = "z"
    OFFSET = "offset"

class TimeTracker:
    def __init__(self):
        self._start = datetime.now()

    def elapsed(self) -> float:
        return (datetime.now() - self._start).total_seconds()

    def reset(self) -> None:
        self._start = datetime.now()

def parse_timecode(value: str) -> float:
    parts = value.split(":")

    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)

    if len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)

    raise ValueError(f"Unsupported timecode format: {value}")

def format_timecode(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60

    return f"{h:02d}:{m:02d}:{s:06.3f}"

def format_datetime_iso_string(value: Union[datetime, int, float], tz_format: TimezoneFormat = TimezoneFormat.ZULU) -> str:
    if isinstance(value, (int, float)):
        value = datetime.fromtimestamp(value, tz=timezone.utc)

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    string = value.astimezone(timezone.utc).isoformat()

    if tz_format == TimezoneFormat.ZULU:
        string = string.replace("+00:00", "Z")

    return string
