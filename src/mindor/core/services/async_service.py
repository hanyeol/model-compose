from typing import Optional, List, Callable, Awaitable, Any
from abc import ABC, abstractmethod
from mindor.core.utils.package import install_package, parse_requirement, is_requirement_satisfied
from threading import Thread
import asyncio, time

class AsyncService(ABC):
    def __init__(self, daemon: bool):
        self.daemon: bool = daemon
        self.started: bool = False

        self.thread: Optional[Thread] = None
        self.thread_loop: Optional[asyncio.AbstractEventLoop] = None
        self.daemon_task: Optional[asyncio.Task] = None

    async def setup(self) -> None:
        dependencies = self._get_setup_requirements()
        if dependencies:
            await self._install_packages(dependencies)

        await self._setup()

    async def teardown(self) -> None:
        await self._teardown()

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

        raise TimeoutError(f"Service did not become ready within {timeout} seconds")

    async def wait_until_stopped(self) -> None:
        if self.thread:
            self.thread.join()

        if self.daemon_task:
            await self.daemon_task

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

    async def _setup(self) -> None:
        pass

    async def _teardown(self) -> None:
        pass

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return None

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

    @abstractmethod
    async def _serve(self) -> None:
        pass

    @abstractmethod
    async def _shutdown(self) -> None:
        pass

    async def _install_packages(self, packages: List[str]) -> None:
        for package_spec in packages:
            package_spec, repository = (package_spec.split("@") + [ None ])[:2]
            requirement = parse_requirement(package_spec)
            if not requirement or not is_requirement_satisfied(requirement):
                await self._install_package(package_spec, repository)
    
    async def _install_package(self, package_spec: str, repository: Optional[str]) -> None:
        await install_package(repository or package_spec)
