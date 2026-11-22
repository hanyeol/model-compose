from __future__ import annotations

from typing import Any, Callable, Dict, Optional
from mindor.dsl.schema.containers.docker import DockerBuildConfig
from mindor.dsl.schema.runtime import DockerRuntimeConfig
from mindor.core.foundation.containers.docker import DockerContainerRunner, DockerImageBuilder, DockerContainerOptions
from mindor.core.foundation.variable.time import parse_time
from .common import CommonRuntime
from .container import ContainerRuntimeBackend
import asyncio

class DockerRuntime(CommonRuntime):
    config: DockerRuntimeConfig

    def __init__(
        self,
        config: DockerRuntimeConfig,
        options: Optional[DockerContainerOptions] = None,
        verbose: bool = False,
    ):
        super().__init__(config, verbose)

        self._stop_timeout = parse_time(config.stop_timeout) if config.stop_timeout is not None else None

        self._runner: DockerContainerRunner = DockerContainerRunner(config.container, options=options, verbose=verbose)
        self._exit_watcher: Optional[asyncio.Task] = None

    @property
    def container_name(self) -> Optional[str]:
        return self._runner.container_name

    async def create(self, tty: bool = True, stdin_open: bool = True) -> None:
        await self._runner.create(tty=tty, stdin_open=stdin_open)

    async def start(self, detach: bool, on_exit: Optional[Callable[[], None]] = None) -> None:
        """Start the container. If `on_exit` is given, it is invoked once the
        container terminates for any reason (normal exit, crash, `docker kill`).

        The docker attach stream does not reliably surface EOF on container
        death — SDK clients can block on `recv()` indefinitely after the
        daemon kills the container. `on_exit` lets the manager close the
        attach socket explicitly so IPC consumers observe the EOF."""
        await self._runner.start(detach=detach)

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

        await self._runner.stop(timeout=self._stop_timeout)

    async def remove(self, force: bool = False) -> None:
        await self._runner.remove(force=force)

    async def exists(self) -> bool:
        return await self._runner.exists()

    async def is_running(self) -> bool:
        return await self._runner.is_running()

    def get_container(self):
        return self._runner.get_container()

    async def _watch_exit(self, on_exit: Callable[[], None]) -> None:
        # Poll the daemon via `docker inspect` subprocess instead of the
        # docker-py client: the attach socket pins a connection in the
        # shared docker-py pool, blocking any further SDK call (including
        # `container.wait()` and `is_running()`) until the attach ends.
        name = self._runner.container_name

        if not name:
            return

        try:
            while True:
                try:
                    await asyncio.sleep(0.5)
                except asyncio.CancelledError:
                    raise

                proc = await asyncio.create_subprocess_exec(
                    "docker", "inspect", "-f", "{{.State.Running}}", name,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                stdout, _ = await proc.communicate()

                if proc.returncode != 0 or stdout.strip() != b"true":
                    break
        except asyncio.CancelledError:
            raise
        except Exception:
            return

        try:
            on_exit()
        except Exception:
            pass

class DockerRuntimeBackend(ContainerRuntimeBackend):
    """Docker-backed `ContainerRuntimeBackend`."""
    runtime_config: DockerRuntimeConfig

    def _create_runtime(self, options: DockerContainerOptions) -> DockerRuntime:
        return DockerRuntime(self.runtime_config, options=options, verbose=self.verbose)

    def _create_builder(self) -> DockerImageBuilder:
        return DockerImageBuilder(verbose=self.verbose)

    def _resolve_container_options(self) -> DockerContainerOptions:
        return DockerContainerOptions()

    def _resolve_build_params(self, config: DockerBuildConfig) -> Dict[str, Any]:
        return {
            "path": config.context,
            "dockerfile": config.dockerfile,
            "build_args": config.args,
            "labels": config.labels,
            "target": config.target,
            "pull": config.pull,
            "cache_from": config.cache_from,
            "network_mode": config.network,
        }
