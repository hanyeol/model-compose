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

    async def _run_worker(self, key: Hashable, queue: asyncio.Queue) -> None:
        while True:
            handler = await queue.get()
            if handler is None:
                return
            try:
                await handler()
            except asyncio.CancelledError:
                raise
            except Exception:
                logging.warning("Event dispatch error for %r", key, exc_info=True)

    def unregister(self, key: Hashable) -> None:
        """Drop the queue/worker for `key` after draining any pending events."""
        queue = self._queues.pop(key, None)
        worker = self._workers.pop(key, None)

        if queue is not None:
            queue.put_nowait(None)

        # worker exits on its own after processing the sentinel; no join here
        # so producers can call this from sync paths without awaiting.
        _ = worker

    async def close(self, timeout: Optional[float] = None) -> None:
        """Stop accepting new events; drain and stop all workers."""
        self._closed = True

        for queue in self._queues.values():
            queue.put_nowait(None)

        workers = list(self._workers.values())
        self._queues.clear()
        self._workers.clear()

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
