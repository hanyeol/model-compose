from typing import Callable, Optional
import asyncio

class ActiveCounter:
    def __init__(self, on_change: Optional[Callable[[int], None]] = None):
        self._count: int = 0
        self._zero_event: asyncio.Event = asyncio.Event()
        self._zero_event.set()
        self._on_change: Optional[Callable[[int], None]] = on_change

    @property
    def count(self) -> int:
        return self._count

    def acquire(self) -> None:
        self._count += 1
        self._zero_event.clear()

        if self._on_change is not None:
            self._on_change(self._count)

    def release(self) -> None:
        self._count -= 1

        if self._count == 0:
            self._zero_event.set()

        if self._on_change is not None:
            self._on_change(self._count)

    async def wait_for_zero(self, timeout: float = 0) -> None:
        if self._count == 0:
            return

        if timeout > 0:
            await asyncio.wait_for(self._zero_event.wait(), timeout=timeout)
        else:
            await self._zero_event.wait()

    def reset(self) -> None:
        self._count = 0
        self._zero_event.set()
