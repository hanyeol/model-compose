from typing import Optional, Callable, Any
from .requirement_manager import RequirementManager
from threading import Thread
import asyncio, functools, time

class AsyncService(RequirementManager):
    def __init__(self, daemon: bool):
        self.daemon: bool = daemon
        self.started: bool = False

        self.daemon_thread: Optional[Thread] = None
        self.daemon_loop: Optional[asyncio.AbstractEventLoop] = None
        self.daemon_task: Optional[asyncio.Task] = None

    async def start(self, background: bool = False) -> None:
        if background:
            def _start_in_thread():
                self.daemon_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.daemon_loop)
                self.daemon_loop.run_until_complete(self._start())

            self.daemon_thread = Thread(target=_start_in_thread)
            self.daemon_thread.start()
        else:
            await self._start()

    async def stop(self) -> None:
        if self.daemon_thread:
            future = asyncio.run_coroutine_threadsafe(self._stop(), self.daemon_loop)
            future.result()
            self.daemon_loop.close()
            self.daemon_loop = None
            self.daemon_thread.join()
            self.daemon_thread = None
        else:
            await self._stop()

    async def wait_until_ready(self, timeout: int = 0) -> None:
        start_time = time.monotonic()

        while timeout <= 0 or time.monotonic() - start_time < timeout:
            if await self._is_ready():
                return
            await asyncio.sleep(0.5)

        raise TimeoutError(f"Service did not become ready within {timeout} seconds")

    async def wait_until_stopped(self) -> None:
        if self.daemon_thread:
            self.daemon_thread.join()

        if self.daemon_task:
            await self.daemon_task

    async def _start(self) -> None:
        self.started = True

        if self.daemon:
            if not self.daemon_thread:
                self.daemon_task = asyncio.create_task(self._serve())
            else:
                await self._serve()

    async def _stop(self) -> None:
        if self.daemon:
            await self._shutdown()

        self.started = False

    async def _is_ready(self) -> bool:
        return True

    async def _serve(self) -> None:
        pass

    async def _shutdown(self) -> None:
        pass

    async def _run_in_executor(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        return await asyncio.get_running_loop().run_in_executor(None, functools.partial(fn, *args, **kwargs))
