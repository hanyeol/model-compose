from types import GeneratorType
from threading import Thread
import asyncio

class AsyncStreamer:
    def __init__(self, generator: GeneratorType, loop: asyncio.AbstractEventLoop):
        self.generator = generator
        self.loop = loop
        self._queue = asyncio.Queue()
        self._end_of_stream = object()

        self._start_stream_watcher()

    def _start_stream_watcher(self):
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
