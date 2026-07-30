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
    - ``stop_event`` is set on ``aclose()`` so the source generator can
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
        stop_event: Optional[Event] = None,
    ):
        self.generator = generator
        self.stop_event = stop_event

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
        self._exhausted = False
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
            self._exhausted = True
            raise StopAsyncIteration

        if isinstance(chunk, BaseException):
            raise chunk

        return chunk

    async def aclose(self) -> None:
        if self.stop_event is not None:
            self.stop_event.set()

        # Producer may be blocked on ``queue.put`` (backpressure) after the
        # consumer left the ``async for`` loop. Drain until end-of-stream so
        # the worker can finish; otherwise ``_thread.join`` would deadlock.
        # If the consumer already drained the queue to completion, skip the
        # drain loop — the sentinel is gone and get() would block forever.
        while not self._exhausted:
            chunk = await self._queue.get()
            if chunk is self._end_of_stream:
                self._exhausted = True
                break

        await asyncio.to_thread(self._thread.join)

class AsyncGeneratorStreamer:
    """Bridges an async iterator produced on a private thread loop into an
    async iterator consumable by the caller's loop.

    A worker thread owns a fresh event loop, calls ``generator`` on it to
    build the source ``AsyncIterator``, and forwards each item into an
    ``asyncio.Queue`` bound to ``loop`` (the loop that will consume this
    stream). Consumers iterate with ``async for`` on the target loop.

    Use this when the source iterator must run on a dedicated loop — e.g. a
    library like Playwright that binds objects to the loop that created them
    and whose async I/O would otherwise block the caller's loop. Building
    the iterator inside ``generator`` ensures resources (browsers, sessions,
    ...) are created on — and bound to — the worker thread's loop.

    Optional features:
    - ``maxsize`` gives the queue a bounded capacity so the producer blocks
      when the consumer falls behind (backpressure).
    - ``stop_event`` is set on ``aclose()`` so the source iterator can
      cooperatively stop (e.g. break out of its loop). Independently,
      ``aclose()`` also cancels the in-flight producer task on the thread
      loop so the source iterator unwinds at its next await; the worker
      thread is joined before ``aclose`` returns.
    - Exceptions raised inside the iterator are forwarded and re-raised out
      of the async iterator.
    """
    def __init__(
        self,
        generator: Callable[[], Awaitable[AsyncIterator[Any]]],
        loop: asyncio.AbstractEventLoop,
        maxsize: int = 0,
        stop_event: Optional[Event] = None,
    ):
        self.generator = generator
        self.stop_event = stop_event

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
        self._exhausted = False
        self._thread_loop: Optional[asyncio.AbstractEventLoop] = None
        self._producer_task: Optional[asyncio.Task] = None
        self._thread = self._start_stream_forwarder(loop)

    @staticmethod
    def _is_running_on_target_loop(loop: asyncio.AbstractEventLoop) -> bool:
        try:
            return asyncio.get_running_loop() is loop
        except RuntimeError:
            return False

    def _start_stream_forwarder(self, loop: asyncio.AbstractEventLoop) -> Thread:
        def _run():
            thread_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(thread_loop)
            self._thread_loop = thread_loop

            async def _produce():
                self._producer_task = asyncio.current_task()
                try:
                    source = await self.generator()  # runs on this thread's loop

                    async for chunk in source:
                        # .result() blocks the producer until the consumer has room,
                        # giving backpressure when maxsize is set.
                        asyncio.run_coroutine_threadsafe(self._queue.put(chunk), loop).result()
                except asyncio.CancelledError:
                    pass
                except BaseException as e:
                    asyncio.run_coroutine_threadsafe(self._queue.put(e), loop).result()
                finally:
                    asyncio.run_coroutine_threadsafe(self._queue.put(self._end_of_stream), loop).result()

            try:
                thread_loop.run_until_complete(_produce())
            finally:
                thread_loop.close()

        thread = Thread(target=_run, daemon=True)
        thread.start()

        return thread

    def __aiter__(self):
        return self

    async def __anext__(self):
        chunk = await self._queue.get()

        if chunk is self._end_of_stream:
            self._exhausted = True
            raise StopAsyncIteration

        if isinstance(chunk, BaseException):
            raise chunk

        return chunk

    async def aclose(self) -> None:
        if self.stop_event is not None:
            self.stop_event.set()

        # Ask the producer task on the thread loop to cancel; the source
        # iterator unwinds at its next await inside _produce().
        if self._producer_task is not None and self._thread_loop is not None:
            try:
                self._thread_loop.call_soon_threadsafe(self._producer_task.cancel)
            except RuntimeError:
                # Thread loop already closed; nothing to cancel.
                pass

        # Producer may be blocked on ``queue.put`` (backpressure) after the
        # consumer left the ``async for`` loop. Drain until end-of-stream so
        # the worker can finish; otherwise ``_thread.join`` would deadlock.
        # If the consumer already drained the queue to completion, skip the
        # drain loop — the sentinel is gone and get() would block forever.
        while not self._exhausted:
            chunk = await self._queue.get()
            if chunk is self._end_of_stream:
                self._exhausted = True
                break

        await asyncio.to_thread(self._thread.join)
