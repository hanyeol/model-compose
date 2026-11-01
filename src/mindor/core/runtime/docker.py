from __future__ import annotations

from typing import Any, Dict, Optional
from mindor.dsl.schema.containers.docker import DockerBuildConfig
from mindor.dsl.schema.runtime import DockerRuntimeConfig
from mindor.core.foundation.containers.docker import DockerContainerRunner, DockerImageBuilder, DockerContainerOptions
from mindor.core.foundation.variable.time import parse_time
from .common import CommonRuntime
from .container import ContainerRuntimeBackend

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

        self._runner: DockerContainerRunner = DockerContainerRunner(config, options=options, verbose=verbose)

    @property
    def container_name(self) -> Optional[str]:
        return self._runner.container_name

    async def create(self, tty: bool = True, stdin_open: bool = True) -> None:
        await self._runner.create(tty=tty, stdin_open=stdin_open)

    async def start(self, detach: bool) -> None:
        await self._runner.start(detach=detach)

    async def stop(self) -> None:
        await self._runner.stop(timeout=self._stop_timeout)

    async def remove(self, force: bool = False) -> None:
        await self._runner.remove(force=force)

    async def exists(self) -> bool:
        return await self._runner.exists()

    async def is_running(self) -> bool:
        return await self._runner.is_running()

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
