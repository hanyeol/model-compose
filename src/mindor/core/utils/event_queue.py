from typing import List, Any
import asyncio

class EventQueue:
    def __init__(self):
        self._events: List[Any] = []
        self._queue: asyncio.Queue = asyncio.Queue()

    def put(self, event: Any) -> None:
        self._queue.put_nowait(event)

    def get(self, consume: bool = True) -> List[Any]:
        events = self._events

        if consume:
            self._events = []

        return events

    def drain(self) -> None:
        while not self._queue.empty():
            self._events.append(self._queue.get_nowait())

    def reset(self) -> None:
        self._events.clear()

        while not self._queue.empty():
            self._queue.get_nowait()

    async def poll(self, timeout: float) -> bool:
        try:
            event = await asyncio.wait_for(self._queue.get(), timeout=timeout)
            self._events.append(event)
            return True
        except asyncio.TimeoutError:
            return False
