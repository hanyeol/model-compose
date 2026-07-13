from typing import Any, Optional, Awaitable, Callable
from types import GeneratorType
from collections.abc import AsyncIterator
from threading import Thread, Event
import asyncio

class SyncGeneratorStreamer:
    """Bridges a blocking sync generator into an async iterator.

    A worker thread drains ``generator`` and forwards each item into an
    ``asyncio.Queue`` bound to ``loop`` (the loop that will consume this
    stream). Consumers iterate with ``async for`` on the target loop.

    Optional features:
    - ``maxsize`` gives the queue a bounded capacity so the producer blocks
      when the consumer falls behind (backpressure).
    - ``cancel_event`` is set on ``aclose()`` so the source generator can
      cooperatively stop; the worker thread is joined before ``aclose``
      returns.
    - Exceptions raised inside the generator are forwarded and re-raised
      out of the async iterator.
    """
    def __init__(
        self,
        generator: GeneratorType,
        loop: asyncio.AbstractEventLoop,
        maxsize: int = 0,
        cancel_event: Optional[Event] = None,
    ):
        self.generator = generator
        self.cancel_event = cancel_event

        # asyncio.Queue must bind to ``loop``. If we're already on it, build
        # inline; otherwise scheduling with .result() from a coroutine on the
        # same loop would deadlock.
        if not self._is_running_on_target_loop(loop):
            async def _create_queue() -> asyncio.Queue:
                return asyncio.Queue(maxsize=maxsize)
            self._queue = asyncio.run_coroutine_threadsafe(_create_queue(), loop).result()
        else:
            self._queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)

        self._end_of_stream = object()
        self._thread = self._start_stream_forwarder(loop)

    @staticmethod
    def _is_running_on_target_loop(loop: asyncio.AbstractEventLoop) -> bool:
        try:
            return asyncio.get_running_loop() is loop
        except RuntimeError:
            return False

    def _start_stream_forwarder(self, loop: asyncio.AbstractEventLoop) -> Thread:
        def _run():
            try:
                for chunk in self.generator:
                    # .result() blocks the producer until the consumer has room,
                    # giving backpressure when maxsize is set.
                    asyncio.run_coroutine_threadsafe(self._queue.put(chunk), loop).result()
            except BaseException as e:
                asyncio.run_coroutine_threadsafe(self._queue.put(e), loop).result()
            finally:
                asyncio.run_coroutine_threadsafe(self._queue.put(self._end_of_stream), loop).result()

        thread = Thread(target=_run, daemon=True)
        thread.start()

        return thread

    def __aiter__(self):
        return self

    async def __anext__(self):
        chunk = await self._queue.get()

        if chunk is self._end_of_stream:
            raise StopAsyncIteration

        if isinstance(chunk, BaseException):
            raise chunk

        return chunk

    async def aclose(self) -> None:
        if self.cancel_event is not None:
            self.cancel_event.set()

        await asyncio.to_thread(self._thread.join)

class AsyncIteratorStreamer:
    def __init__(self, source: AsyncIterator[Any], worker: Callable[[Any], Awaitable[Any]]):
        self.source = source
        self.worker = worker

    async def __aiter__(self) -> AsyncIterator[Any]:
        async for item in self.source:
            yield await self.worker(item)
