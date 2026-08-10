from typing import Union, Optional, List, Any
from collections.abc import AsyncIterator
from ..streaming.iterators import StreamIterator, StreamChunkIterator

class DecimalValueRenderer:
    async def render(
        self,
        value: Any,
        default: Optional[int] = None
    ) -> Optional[Union[int, List[Optional[int]], AsyncIterator[Optional[int]]]]:
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

    async def _render_element(self, value: Any, default: Optional[int] = None) -> Optional[int]:
        if value is not None:
            return parse_decimal(value)

        return default

def parse_decimal(value: Union[str, int, float]) -> int:
    """Parse a value with an SI decimal suffix into an integer.

    Uses SI (decimal) units: 1k = 1000, 1M = 1_000_000, 1G = 1_000_000_000.
    Suitable for bitrates, sample rates, token counts, and similar values that
    follow the decimal-scale convention rather than binary (1024-based) scaling.
    """
    if isinstance(value, (float, int)):
        return int(value)

    if value.endswith("G") or value.endswith("g"):
        return int(float(value[:-1]) * 1_000_000_000)

    if value.endswith("M") or value.endswith("m"):
        return int(float(value[:-1]) * 1_000_000)

    if value.endswith("K") or value.endswith("k"):
        return int(float(value[:-1]) * 1_000)

    raise ValueError(f"Unsupported decimal format: {value}")
