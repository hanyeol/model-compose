from typing import Optional, Callable, Awaitable, Any
from abc import ABC, abstractmethod
from threading import Thread
import asyncio, time

class AsyncService(ABC):
    def __init__(self, daemon: bool):
        self.daemon: bool = daemon
        self.started: bool = False

        self.thread: Optional[Thread] = None
        self.thread_loop: Optional[asyncio.AbstractEventLoop] = None
        self.daemon_task: Optional[asyncio.Task] = None

    async def start(self, background: bool = False) -> None:
        if background:
            def _start_in_thread():
                self.thread_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.thread_loop)
                self.thread_loop.run_until_complete(self._start())
    
            self.thread = Thread(target=_start_in_thread)
            self.thread.start()
        else:
            await self._start()

    async def stop(self) -> None:
        if self.thread:
            future = asyncio.run_coroutine_threadsafe(self._stop(), self.thread_loop)
            future.result()
            self.thread_loop.close()
            self.thread_loop = None
            self.thread.join()
            self.thread = None
        else:
            await self._stop()

    async def wait_until_ready(self, timeout: int = 0) -> None:
        start_time = time.monotonic()

        while timeout <= 0 or time.monotonic() - start_time < timeout:
            if await self._is_ready():
                return
            await asyncio.sleep(0.5)

        raise TimeoutError(f"Service did not become ready within {timeout} seconds.")

    async def wait_until_stopped(self) -> None:
        if self.thread:
            self.thread.join()

        if self.daemon_task:
            await self.daemon_task

        await self._on_stop()

    def run_in_thread(self, runner: Callable[[], Awaitable[Any]]) -> asyncio.Future:
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()

        def _start_in_thread():
            thread_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(thread_loop)

            async def _run_and_set_result():
                try:
                    result = await runner()
                    loop.call_soon_threadsafe(future.set_result, result)
                except Exception as e:
                    loop.call_soon_threadsafe(future.set_exception, e)

            thread_loop.run_until_complete(_run_and_set_result())

        thread = Thread(target=_start_in_thread)
        thread.start()

        return future

    async def _start(self) -> None:
        self.started = True

        if self.daemon:
            if not self.thread:
                self.daemon_task = asyncio.create_task(self._serve())
            else:
                await self._serve()

    async def _stop(self) -> None:
        if self.daemon:
            await self._shutdown()

        self.started = False

    async def _is_ready(self) -> bool:
        return True

    async def _on_stop(self) -> None:
        pass

    @abstractmethod
    async def _serve(self) -> None:
        pass

    @abstractmethod
    async def _shutdown(self) -> None:
        pass
