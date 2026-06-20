from typing import Any, Awaitable, Callable
from types import GeneratorType
from collections.abc import AsyncIterator
from threading import Thread
import asyncio

class SyncGeneratorStreamer:
    def __init__(self, generator: GeneratorType, loop: asyncio.AbstractEventLoop):
        self.generator = generator
        self.loop = loop
        self._queue = asyncio.Queue()
        self._end_of_stream = object()

        self._start_stream_forwarder()

    def _start_stream_forwarder(self):
        def _run():
            for chunk in self.generator:
                asyncio.run_coroutine_threadsafe(self._queue.put(chunk), self.loop)
            asyncio.run_coroutine_threadsafe(self._queue.put(self._end_of_stream), self.loop)

        Thread(target=_run, daemon=True).start()

    def __aiter__(self):
        return self

    async def __anext__(self):
        chunk = await self._queue.get()
        if chunk is self._end_of_stream:
            raise StopAsyncIteration
        return chunk

class AsyncIteratorStreamer:
    def __init__(self, source: AsyncIterator[Any], worker: Callable[[Any], Awaitable[Any]]):
        self.source = source
        self.worker = worker

    async def __aiter__(self) -> AsyncIterator[Any]:
        async for item in self.source:
            yield await self.worker(item)
