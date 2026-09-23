from typing import Union, Optional, List, Any
from collections.abc import AsyncIterator
from ..streaming.iterators import StreamIterator, StreamChunkIterator

class SizeValueRenderer:
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
            return parse_size(value)

        return default

def parse_size(value: Union[str, int, float]) -> int:
    if isinstance(value, (float, int)):
        return int(value)

    if value.endswith("GB"):
        return int(float(value[:-2]) * 1024 ** 3)

    if value.endswith("G"):
        return int(float(value[:-1]) * 1024 ** 3)

    if value.endswith("MB"):
        return int(float(value[:-2]) * 1024 ** 2)

    if value.endswith("M"):
        return int(float(value[:-1]) * 1024 ** 2)

    if value.endswith("KB"):
        return int(float(value[:-2]) * 1024)

    if value.endswith("K"):
        return int(float(value[:-1]) * 1024)

    if value.endswith("B"):
        return int(float(value[:-1]))

    # Bare numeric strings ("1024", "2048.0") are treated as bytes.
    try:
        return int(float(value))
    except ValueError:
        raise ValueError(f"Unsupported size format: {value}")
