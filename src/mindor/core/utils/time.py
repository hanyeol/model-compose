from typing import Union, Optional
from datetime import timedelta, datetime
import zoneinfo

class TimeTracker:
    def __init__(self):
        self._start = datetime.now()

    def elapsed(self) -> float:
        return (datetime.now() - self._start).total_seconds()

    def reset(self) -> None:
        self._start = datetime.now()

def parse_duration(value: Union[str, float, int]) -> timedelta:
    if isinstance(value, (float, int)):
        return timedelta(seconds=value)

    if value.endswith("s"):
        return timedelta(seconds=float(value[:-1]))
    
    if value.endswith("m"):
        return timedelta(minutes=float(value[:-1]))
    
    if value.endswith("h"):
        return timedelta(hours=float(value[:-1]))
    
    if value.endswith("d"):
        return timedelta(days=float(value[:-1]))

    raise ValueError(f"Unsupported duration format: {value}")

def parse_datetime(value: Union[str, datetime], timezone: Optional[str]) -> datetime:
    time = datetime.fromisoformat(value) if isinstance(value, str) else value
    
    if timezone and time.tzinfo is None:
        time = time.replace(tzinfo=zoneinfo.ZoneInfo(timezone))

    return time
