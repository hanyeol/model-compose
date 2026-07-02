from __future__ import annotations

from typing import Any, Dict, Optional
from dataclasses import dataclass
from mindor.dsl.schema.containers.docker import DockerBuildConfig
from mindor.dsl.schema.runtime import DockerRuntimeConfig
from mindor.core.foundation.containers.docker import (
    DockerContainerParams,
    DockerContainerRunner,
    DockerImageBuilder,
)
from mindor.core.foundation.variable.time import parse_duration
from .common import ContainerRuntimeBackend

@dataclass
class DockerRuntimeParams(DockerContainerParams):
    start_timeout: Optional[float] = None
    stop_timeout: Optional[float] = None

    @classmethod
    def from_config(cls, config: DockerRuntimeConfig) -> DockerRuntimeParams:
        return cls(
            **DockerContainerParams.from_config(config).__dict__,
            start_timeout=parse_duration(config.start_timeout),
            stop_timeout=parse_duration(config.stop_timeout),
        )

class DockerRuntime(DockerContainerRunner):
    def __init__(self, params: DockerRuntimeParams, verbose: bool = False):
        super().__init__(params, verbose=verbose)

        self.params: DockerRuntimeParams = params

    async def stop(self) -> None:
        await super().stop(timeout=self.params.stop_timeout)

class DockerRuntimeBackend(ContainerRuntimeBackend):
    """Docker-backed `ContainerRuntimeBackend`."""
    _runtime_config: DockerRuntimeConfig

    def _create_runtime(self, params: DockerRuntimeParams) -> DockerRuntime:
        return DockerRuntime(params, verbose=self.verbose)

    def _resolve_runtime_params(self) -> DockerRuntimeParams:
        return DockerRuntimeParams.from_config(self._runtime_config)

    def _create_builder(self) -> DockerImageBuilder:
        return DockerImageBuilder(verbose=self.verbose)

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
