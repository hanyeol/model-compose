from typing import Union, Optional, List, Any
from collections.abc import AsyncIterator
from mindor.core.utils.time import parse_timecode
from datetime import datetime, timedelta
from ..streaming.iterators import StreamIterator, StreamChunkIterator
import zoneinfo

class TimeValueRenderer:
    async def render(
        self,
        value: Any,
        default: Optional[float] = None
    ) -> Optional[Union[float, List[Optional[float]], AsyncIterator[Optional[float]]]]:
        if isinstance(value, (StreamIterator, AsyncIterator)):
            async def _iterate():
                async for chunk in value:
                    yield await self._render_element(chunk, default)

            # Preserve StreamChunkIterator type for downstream isinstance checks.
            if isinstance(value, StreamChunkIterator):
                return StreamChunkIterator(_iterate(), is_fragmented=value.is_fragmented)

            return _iterate()

        if isinstance(value, (list, tuple)):
            return [ await self._render_element(item, default) for item in value ]

        return await self._render_element(value, default)

    async def _render_element(self, value: Any, default: Optional[float] = None) -> Optional[float]:
        if value is not None:
            return parse_time(value)

        return default

def parse_time(value: Union[str, float, int]) -> float:
    if isinstance(value, (float, int)):
        return timedelta(seconds=value).total_seconds()

    if ":" in value:
        return parse_timecode(value)

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

    # Bare numeric strings ("30", "1.5") are treated as seconds.
    try:
        return timedelta(seconds=float(value)).total_seconds()
    except ValueError:
        raise ValueError(f"Unsupported duration format: {value}")

def parse_datetime(value: Union[str, datetime], timezone: Optional[str]) -> datetime:
    time = datetime.fromisoformat(value) if isinstance(value, str) else value

    if timezone and time.tzinfo is None:
        time = time.replace(tzinfo=zoneinfo.ZoneInfo(timezone))

    return time
