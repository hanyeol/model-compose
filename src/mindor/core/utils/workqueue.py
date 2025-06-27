from typing import Callable, Awaitable, Tuple, Dict, List, Any
import asyncio

class WorkQueue:
    def __init__(self, max_concurrent_count: int, handler: Callable[..., Awaitable[Any]]):
        self.queue: asyncio.Queue[Tuple[Tuple[Any, ...], Dict[str, Any], asyncio.Future]] = None
        self.max_concurrent_count: int = max_concurrent_count
        self.handler: Callable[..., Awaitable[Any]] = handler
        self.workers: List[asyncio.Task] = []
        self.stopped: bool = False

    async def _worker(self):
        while not self.stopped:
            try:
                args, kwargs, future = await self.queue.get()
                try:
                    result = await self.handler(*args, **kwargs)
                    future.set_result(result)
                except Exception as e:
                    future.set_exception(e)
                finally:
                    self.queue.task_done()
            except asyncio.CancelledError:
                break

    async def start(self):
        if self.queue:
            raise ValueError("Queue already started.")

        self.queue = asyncio.Queue()
        self.stopped = False

        for _ in range(self.max_concurrent_count):
            self.workers.append(asyncio.create_task(self._worker()))

    async def schedule(self, *args: Any, **kwargs: Any) -> asyncio.Future:
        if not self.queue:
            raise ValueError("Queue not started.")

        future = asyncio.get_running_loop().create_future()
        await self.queue.put((args, kwargs, future))
        
        return future

    async def stop(self):
        if not self.queue:
            raise ValueError("Queue already stopped or not started.")
        
        self.stopped = True
        for worker in self.workers:
            worker.cancel()

        await asyncio.gather(*self.workers, return_exceptions=True)

        self.workers = []
        self.queue = None
