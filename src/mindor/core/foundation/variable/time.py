from typing import Union, Optional
from mindor.core.utils.time import parse_timecode
from datetime import datetime, timedelta
import zoneinfo

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

def parse_time(value: Union[str, float, int]) -> float:
    if isinstance(value, str) and ":" in value:
        return parse_timecode(value)

    return parse_duration(value)
