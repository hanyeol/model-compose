from __future__ import annotations

from typing import Any, Dict, Optional
from mindor.dsl.schema.containers.apple_container import AppleContainerBuildConfig
from mindor.dsl.schema.runtime import AppleContainerRuntimeConfig
from mindor.core.foundation.containers.apple_container import (
    AppleContainerOptions,
    AppleContainerRunner,
    AppleContainerImageBuilder,
)
from mindor.core.foundation.variable.time import parse_time
from .common import CommonRuntime
from .container import ContainerRuntimeBackend

class AppleContainerRuntime(CommonRuntime):
    config: AppleContainerRuntimeConfig

    def __init__(
        self,
        config: AppleContainerRuntimeConfig,
        options: Optional[AppleContainerOptions] = None,
        verbose: bool = False,
    ):
        super().__init__(config, verbose)

        self._stop_timeout = parse_time(config.stop_timeout) if config.stop_timeout is not None else None

        self._runner: AppleContainerRunner = AppleContainerRunner(config, options=options, verbose=verbose)

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

class AppleContainerRuntimeBackend(ContainerRuntimeBackend):
    """Apple Container-backed `ContainerRuntimeBackend`."""
    runtime_config: AppleContainerRuntimeConfig

    def _create_runtime(self, options: AppleContainerOptions) -> AppleContainerRuntime:
        return AppleContainerRuntime(self.runtime_config, options=options, verbose=self.verbose)

    def _create_builder(self) -> AppleContainerImageBuilder:
        return AppleContainerImageBuilder(verbose=self.verbose)

    def _resolve_container_options(self) -> AppleContainerOptions:
        return AppleContainerOptions()

    def _resolve_build_params(self, config: AppleContainerBuildConfig) -> Dict[str, Any]:
        return {
            "path": config.context,
            "dockerfile": config.dockerfile,
            "build_args": config.args,
            "target": config.target,
            "labels": config.labels,
            "pull": config.pull,
        }
