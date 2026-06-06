from typing import Union, Optional
from datetime import datetime, timedelta, timezone
from enum import Enum
import zoneinfo

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

def parse_duration(value: Union[str, float, int]) -> float:
    if isinstance(value, (float, int)):
        return timedelta(seconds=value).total_seconds()

    if value.endswith("ms"):
        return timedelta(milliseconds=float(value[:-2])).total_seconds()

    if value.endswith("s"):
        return timedelta(seconds=float(value[:-1])).total_seconds()

    if value.endswith("m"):
        return timedelta(minutes=float(value[:-1])).total_seconds()

    if value.endswith("h"):
        return timedelta(hours=float(value[:-1])).total_seconds()

    if value.endswith("d"):
        return timedelta(days=float(value[:-1])).total_seconds()

    raise ValueError(f"Unsupported duration format: {value}")

def parse_datetime(value: Union[str, datetime], timezone: Optional[str]) -> datetime:
    time = datetime.fromisoformat(value) if isinstance(value, str) else value

    if timezone and time.tzinfo is None:
        time = time.replace(tzinfo=zoneinfo.ZoneInfo(timezone))

    return time

def parse_timecode(value: Union[str, float, int]) -> float:
    if isinstance(value, str) and ":" in value:
        parts = value.split(":")
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        if len(parts) == 2:
            m, s = parts
            return int(m) * 60 + float(s)
        raise ValueError(f"Unsupported timecode format: {value}")

    return parse_duration(value)

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
