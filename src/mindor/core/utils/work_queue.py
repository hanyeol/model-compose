from typing import Callable, Awaitable, Tuple, Dict, List, Any
from .active_counter import ActiveCounter
import asyncio

class WorkQueue:
    def __init__(self, max_concurrent_count: int, handler: Callable[..., Awaitable[Any]]):
        self.queue: asyncio.Queue[Tuple[Tuple[Any, ...], Dict[str, Any], asyncio.Future]] = None
        self.max_concurrent_count: int = max_concurrent_count
        self.handler: Callable[..., Awaitable[Any]] = handler
        self.workers: List[asyncio.Task] = []
        self.stopped: bool = False
        self.draining: bool = False
        self._active_counter: ActiveCounter = ActiveCounter()

    async def _worker(self):
        while not self.stopped:
            try:
                args, kwargs, future = await self.queue.get()

                if self.draining:
                    if not future.done():
                        future.set_exception(RuntimeError("Service is shutting down"))
                    self.queue.task_done()
                    continue

                self._active_counter.acquire()

                try:
                    result = await self.handler(*args, **kwargs)
                    if not future.done():
                        future.set_result(result)
                except Exception as e:
                    if not future.done():
                        future.set_exception(e)
                finally:
                    self.queue.task_done()
                    self._active_counter.release()
            except asyncio.CancelledError:
                break

    async def start(self):
        if self.queue:
            raise ValueError("Queue already started")

        self.queue = asyncio.Queue()
        self.stopped = False
        self.draining = False

        self._active_counter.reset()

        for _ in range(self.max_concurrent_count):
            self.workers.append(asyncio.create_task(self._worker()))

    async def schedule(self, *args: Any, **kwargs: Any) -> asyncio.Future:
        if not self.queue:
            raise ValueError("Queue not started")

        if self.draining or self.stopped:
            raise RuntimeError("Queue is shutting down")

        future = asyncio.get_running_loop().create_future()
        await self.queue.put((args, kwargs, future))

        return future

    async def stop(self, timeout: float = 30.0):
        if not self.queue:
            raise ValueError("Queue not started")

        # Phase 1: drain — reject new work, wait for active handlers to finish
        self.draining = True

        try:
            await self._active_counter.wait_for_zero(timeout=timeout)
        except asyncio.TimeoutError:
            pass

        # Phase 2: force-stop
        self.stopped = True
        for worker in self.workers:
            worker.cancel()

        await asyncio.gather(*self.workers, return_exceptions=True)

        # Reject remaining queued items
        while not self.queue.empty():
            try:
                args, kwargs, future = self.queue.get_nowait()
                if not future.done():
                    future.set_exception(RuntimeError("Service shut down"))
                self.queue.task_done()
            except asyncio.QueueEmpty:
                break

        self.workers = []
        self.queue = None
