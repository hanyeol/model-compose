from typing import Optional, Callable, Awaitable, Dict, Literal, Any
from dataclasses import dataclass
from threading import Lock
import asyncio

@dataclass
class InterruptPoint:
    task_id: str
    job_id: str
    phase: Literal["before", "after"]
    message: Optional[str]
    metadata: Optional[Dict[str, Any]]
    future: asyncio.Future

class InterruptHandler:
    def __init__(self, callback: Optional[Callable[[InterruptPoint], Awaitable[None]]] = None):
        self._points: Dict[str, InterruptPoint] = {}
        self._lock: Lock = Lock()
        self._callback: Optional[Callable[[InterruptPoint], Awaitable[None]]] = callback

    async def interrupt(self, point: InterruptPoint) -> Any:
        key = f"{point.task_id}:{point.job_id}:{point.phase}"
        with self._lock:
            self._points[key] = point

        if self._callback:
            await self._callback(point)

        return await point.future

    def resolve(self, task_id: str, job_id: str, answer: Any) -> bool:
        with self._lock:
            point = self._pop_point(task_id, job_id)

        if point is None:
            return False

        loop = point.future.get_loop()
        loop.call_soon_threadsafe(point.future.set_result, answer)

        return True

    def _pop_point(self, task_id: str, job_id: str) -> Optional[InterruptPoint]:
        for key, point in self._points.items():
            if point.task_id == task_id and point.job_id == job_id:
                return self._points.pop(key)
        return None
