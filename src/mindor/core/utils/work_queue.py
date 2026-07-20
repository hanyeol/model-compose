from typing import Callable, Awaitable, Tuple, Dict, List, Any
from .active_counter import ActiveCounter
from mindor.core.errors import ShutdownError
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
            except asyncio.CancelledError:
                break

            try:
                # Skip work that was cancelled while queued — never invoke handler.
                if future.cancelled():
                    continue

                # Run the handler in a child task and await it as an
                # awaitable, so a CancelledError raised inside the handler
                # (e.g. cooperative workflow cancel) reports on the child
                # task without cancelling this worker.
                handler_task = asyncio.ensure_future(self.handler(*args, **kwargs))

                # Forward a cancel on the future to the running handler so an
                # in-flight action stops promptly instead of running to completion.
                # Bind handler_task explicitly — a closure over the loop-local
                # variable would rebind on the next iteration.
                def _forward_cancel(future: asyncio.Future, handler_task=handler_task) -> None:
                    if future.cancelled() and not handler_task.done():
                        handler_task.cancel()
                future.add_done_callback(_forward_cancel)

                try:
                    await asyncio.wait({handler_task})
                    if handler_task.cancelled():
                        if not future.done():
                            future.cancel()
                    elif handler_task.exception() is not None:
                        if not future.done():
                            future.set_exception(handler_task.exception())
                    else:
                        if not future.done():
                            future.set_result(handler_task.result())
                finally:
                    future.remove_done_callback(_forward_cancel)
            finally:
                self.queue.task_done()
                self._active_counter.release()

    async def start(self):
        if self.queue:
            raise RuntimeError("Queue already started")

        self.queue = asyncio.Queue()
        self.stopped = False
        self.draining = False

        self._active_counter.reset()

        for _ in range(self.max_concurrent_count):
            self.workers.append(asyncio.create_task(self._worker()))

    async def schedule(self, *args: Any, **kwargs: Any) -> asyncio.Future:
        if not self.queue:
            raise RuntimeError("Queue not started")

        if self.draining or self.stopped:
            raise ShutdownError("Queue is shutting down")

        future = asyncio.get_running_loop().create_future()
        self._active_counter.acquire()
        await self.queue.put((args, kwargs, future))

        return future

    async def stop(self, timeout: float = 30.0):
        if not self.queue:
            raise RuntimeError("Queue not started")

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
                    future.set_exception(ShutdownError("Service shut down"))
                self.queue.task_done()
            except asyncio.QueueEmpty:
                break

        self.workers = []
        self.queue = None
