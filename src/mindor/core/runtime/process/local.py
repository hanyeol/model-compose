from __future__ import annotations

from typing import Any, Callable, Optional
from mindor.dsl.schema.runtime import ProcessRuntimeConfig
from mindor.core.foundation.variable.time import parse_time
from ..common import CommonRuntime
from multiprocessing import Process
import asyncio, multiprocessing, os

# Use `spawn` explicitly. Linux defaults to `fork`, which duplicates the entire
# parent state (open fds, threads, partially-initialized CUDA / asyncio loops,
# multiprocessing exit hooks). That has caused runaway child re-spawns and
# blocks the controller shutdown path. `spawn` starts a fresh executable and
# only receives what we pass through pickled args.
_SPAWN_CONTEXT = multiprocessing.get_context("spawn")

class LocalProcessRuntime(CommonRuntime):
    """Generic lifecycle wrapper around a `multiprocessing.Process`.

    Pure lifecycle — knows nothing about IPC protocols, codecs, or channels.
    Callers provide an `entrypoint` callable and `args` (commonly used to
    pass `Queue` handles captured at construction time on the parent side)
    and decide how to communicate with the child.

    Typical flow:
        runtime = LocalProcessRuntime(entrypoint=_child_main, args=(queue_in, queue_out), config=config)
        await runtime.start()
        ...
        await runtime.stop()
    """
    config: ProcessRuntimeConfig

    def __init__(
        self,
        entrypoint: Callable[..., Any],
        args: tuple,
        config: ProcessRuntimeConfig,
        verbose: bool = False,
    ):
        super().__init__(config, verbose)

        self.entrypoint = entrypoint
        self.args = args

        self._stop_timeout = parse_time(config.stop_timeout) if config.stop_timeout is not None else None

        self._subprocess: Optional[Process] = None
        self._exit_watcher: Optional[asyncio.Task] = None

    async def start(self, on_exit: Optional[Callable[[], None]] = None) -> None:
        """Spawn the subprocess. If `on_exit` is given, it is invoked once the
        subprocess terminates for any reason (normal exit, crash, SIGKILL).

        `on_exit` lets IPC transports that can't observe writer death on their
        own — notably `multiprocessing.Queue`, where the parent still holds
        a writer fd — bridge the gap with a watcher task owned by the runtime."""
        if self.config.env:
            for key, value in self.config.env.items():
                os.environ[key] = value

        self._subprocess = _SPAWN_CONTEXT.Process(
            target=self.entrypoint,
            args=self.args,
            daemon=False,
        )
        self._subprocess.start()

        if on_exit is not None:
            self._exit_watcher = asyncio.create_task(self._watch_exit(on_exit))

    async def stop(self) -> None:
        if self._exit_watcher is not None:
            self._exit_watcher.cancel()

            try:
                await self._exit_watcher
            except (asyncio.CancelledError, Exception):
                pass

            self._exit_watcher = None

        if self._subprocess is None:
            return

        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._subprocess.join(timeout=self._stop_timeout),
            )
        except Exception:
            pass

        if self._subprocess.is_alive():
            self._subprocess.terminate()
            self._subprocess.join(timeout=5)

            if self._subprocess.is_alive():
                self._subprocess.kill()

    async def _watch_exit(self, on_exit: Callable[[], None]) -> None:
        subprocess = self._subprocess

        if subprocess is None:
            return

        try:
            await asyncio.get_event_loop().run_in_executor(None, subprocess.join)
        except asyncio.CancelledError:
            raise
        except Exception:
            return

        try:
            on_exit()
        except Exception:
            pass

    @property
    def is_alive(self) -> bool:
        return self._subprocess is not None and self._subprocess.is_alive()

    @property
    def subprocess(self) -> Optional[Process]:
        return self._subprocess
