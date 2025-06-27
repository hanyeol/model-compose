from typing import Optional
from abc import ABC, abstractmethod
from threading import Thread
import asyncio

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

    async def wait_until_stopped(self) -> None:
        if self.thread:
            self.thread.join()

        if self.daemon_task:
            await self.daemon_task

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

    @abstractmethod
    async def _serve(self) -> None:
        pass

    @abstractmethod
    async def _shutdown(self) -> None:
        pass
