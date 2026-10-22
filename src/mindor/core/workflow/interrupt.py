from typing import Optional, Callable, Awaitable, Dict, List, Literal, Any, Set
from dataclasses import dataclass
from threading import Lock
import asyncio

@dataclass
class InterruptPoint:
    id: str
    task_id: str
    job_id: str
    run_id: Optional[str]
    phase: Literal[ "before", "after" ]
    message: Optional[str]
    metadata: Optional[Dict[str, Any]]
    future: asyncio.Future

class InterruptHandler:
    def __init__(
        self,
        callback: Optional[Callable[[List["InterruptPoint"]], Awaitable[None]]] = None,
        on_job_interrupted: Optional[Callable[["InterruptPoint"], None]] = None,
        on_interrupt_resolved: Optional[Callable[["InterruptPoint"], None]] = None,
    ):
        self._points: Dict[str, InterruptPoint] = {}
        self._pending_points: Dict[str, InterruptPoint] = {}
        self._lock: Lock = Lock()
        self._callback: Optional[Callable[[List[InterruptPoint]], Awaitable[None]]] = callback
        self._on_job_interrupted: Optional[Callable[[InterruptPoint], None]] = on_job_interrupted
        self._on_interrupt_resolved: Optional[Callable[[InterruptPoint], None]] = on_interrupt_resolved

    async def interrupt(self, point: InterruptPoint) -> Any:
        with self._lock:
            self._points[point.id] = point
            self._pending_points[point.id] = point

        if self._on_job_interrupted:
            self._on_job_interrupted(point)

        try:
            return await point.future
        finally:
            if self._on_interrupt_resolved:
                self._on_interrupt_resolved(point)

    async def flush(self) -> None:
        """Invoke the callback with every point that has entered since the last flush."""
        with self._lock:
            points = list(self._pending_points.values())
            self._pending_points.clear()

        if points and self._callback:
            await self._callback(points)

    def resolve(self, task_id: str, answers: Optional[Dict[str, Any]] = None) -> Set[str]:
        points: List[tuple[InterruptPoint, Any]] = []

        with self._lock:
            if answers is not None:
                for id, answer in answers.items():
                    point = self._points.pop(id, None)

                    if point is None:
                        continue

                    if point.task_id != task_id:
                        # id collision across tasks is not supported — put it back.
                        self._points[id] = point
                        continue

                    # Resolved points are no longer eligible for the next flush.
                    self._pending_points.pop(id, None)
                    points.append((point, answer))
            else:
                for point in self._pop_points_for_task(task_id):
                    points.append((point, None))

        for point, answer in points:
            loop = point.future.get_loop()
            loop.call_soon_threadsafe(point.future.set_result, answer)

        return { point.id for point, _ in points }

    def cancel(self, task_id: str) -> None:
        with self._lock:
            points = self._pop_points_for_task(task_id)

        for point in points:
            if point.future.done():
                continue

            loop = point.future.get_loop()
            loop.call_soon_threadsafe(point.future.cancel)

    def points_for_task(self, task_id: str) -> List[InterruptPoint]:
        with self._lock:
            return [ point for point in self._points.values() if point.task_id == task_id ]

    def set_on_job_interrupted(self, callback: Optional[Callable[[InterruptPoint], None]]) -> None:
        with self._lock:
            self._on_job_interrupted = callback

    def set_on_interrupt_resolved(self, callback: Optional[Callable[[InterruptPoint], None]]) -> None:
        with self._lock:
            self._on_interrupt_resolved = callback

    def _pop_points_for_task(self, task_id: str) -> List[InterruptPoint]:
        points: List[InterruptPoint] = []

        for id in [ id for id, point in self._points.items() if point.task_id == task_id ]:
            points.append(self._points.pop(id))
            self._pending_points.pop(id, None)

        return points
