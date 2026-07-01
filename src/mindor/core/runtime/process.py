from typing import Any, Callable, Dict, Optional
from dataclasses import dataclass, field
from multiprocessing import Process
import asyncio, os

@dataclass
class ProcessRuntimeParams:
    """Parameters for spawning and stopping a child Python process."""
    env: Dict[str, str] = field(default_factory=dict)
    start_timeout: float = 60.0
    stop_timeout: float = 30.0

class ProcessRuntime:
    """Generic lifecycle wrapper around a `multiprocessing.Process`.

    Pure lifecycle — knows nothing about IPC protocols, codecs, or channels.
    Callers provide `target` and `args` (commonly used to pass `Queue` handles
    captured at construction time on the parent side) and decide how to
    communicate with the child.

    Typical flow:
        runtime = ProcessRuntime(target=_child_main, args=(queue_in, queue_out), params=ProcessRuntimeParams())
        await runtime.start()
        ...
        await runtime.stop()
    """
    def __init__(
        self,
        target: Callable[..., Any],
        args: tuple,
        params: ProcessRuntimeParams,
        verbose: bool = False,
    ):
        self.target = target
        self.args = args
        self.params = params
        self.verbose = verbose

        self._subprocess: Optional[Process] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def start(self) -> None:
        self._loop = asyncio.get_event_loop()

        if self.params.env:
            for key, value in self.params.env.items():
                os.environ[key] = value

        self._subprocess = Process(
            target=self.target,
            args=self.args,
            daemon=False,
        )
        self._subprocess.start()

    async def stop(self) -> None:
        if self._subprocess is None:
            return

        try:
            await self._loop.run_in_executor(
                None,
                lambda: self._subprocess.join(timeout=self.params.stop_timeout),
            )
        except Exception:
            pass

        if self._subprocess.is_alive():
            self._subprocess.terminate()
            self._subprocess.join(timeout=5)
            if self._subprocess.is_alive():
                self._subprocess.kill()

    @property
    def is_alive(self) -> bool:
        return self._subprocess is not None and self._subprocess.is_alive()

    @property
    def subprocess(self) -> Optional[Process]:
        return self._subprocess
