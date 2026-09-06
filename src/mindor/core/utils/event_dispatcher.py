from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Hashable, Optional
from mindor.core.logger import logging
import asyncio

EventHandler = Callable[[], Awaitable[None]]

class EventDispatcher:
    """Serialize event delivery per subscriber via a queue-and-worker pair.

    Producers call `dispatch(key, handler)`; the coroutine returned by
    `handler()` runs on a worker task owned by `key`. Events sharing a key
    run in FIFO order; events with different keys run concurrently.
    `handler` is a zero-arg coroutine factory so producers can bind whatever
    payload they need at call time.
    """
    def __init__(self):
        self._queues: Dict[Hashable, asyncio.Queue] = {}
        self._workers: Dict[Hashable, asyncio.Task] = {}
        # Retain strong refs so unregister/GC can't drop an in-flight worker
        # before it processes its sentinel (asyncio only keeps weak refs).
        self._detached_workers: set[asyncio.Task] = set()
        self._closed: bool = False

    def dispatch(self, key: Hashable, handler: EventHandler) -> None:
        if self._closed:
            return

        queue = self._queues.get(key)

        if queue is None:
            queue = asyncio.Queue()
            self._queues[key] = queue
            self._workers[key] = asyncio.create_task(self._run_worker(key, queue))

        queue.put_nowait(handler)

    async def join(self, key: Hashable) -> None:
        """Wait until all handlers currently queued for `key` have been processed."""
        queue = self._queues.get(key)

        if queue is None:
            return

        await queue.join()

    async def _run_worker(self, key: Hashable, queue: asyncio.Queue) -> None:
        while True:
            handler = await queue.get()
            try:
                if handler is None:
                    return
                try:
                    await handler()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logging.warning("Event dispatch error for %r", key, exc_info=True)
            finally:
                queue.task_done()

    def unregister(self, key: Hashable) -> None:
        """Drop the queue/worker for `key` after draining any pending events."""
        queue = self._queues.pop(key, None)
        worker = self._workers.pop(key, None)

        if queue is not None:
            queue.put_nowait(None)

        # Move the worker into a strong-ref set so it survives until the
        # sentinel is processed; producers stay on sync paths (no await).
        if worker is not None:
            self._detached_workers.add(worker)
            worker.add_done_callback(self._detached_workers.discard)

    async def close(self, timeout: Optional[float] = None) -> None:
        """Stop accepting new events; drain and stop all workers."""
        self._closed = True

        for queue in self._queues.values():
            queue.put_nowait(None)

        workers = list(self._workers.values()) + list(self._detached_workers)
        self._queues.clear()
        self._workers.clear()
        self._detached_workers.clear()

        if not workers:
            return

        try:
            await asyncio.wait_for(
                asyncio.gather(*workers, return_exceptions=True),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            for worker in workers:
                if not worker.done():
                    worker.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
