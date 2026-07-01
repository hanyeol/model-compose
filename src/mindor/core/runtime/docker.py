from __future__ import annotations

from typing import Any, Dict, Optional
from dataclasses import dataclass
from mindor.dsl.schema.containers.docker import DockerBuildConfig
from mindor.dsl.schema.runtime import DockerRuntimeConfig
from mindor.core.foundation.containers.docker import (
    DockerBuildParams,
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
    def _create_runtime(self, params: DockerRuntimeParams) -> DockerRuntime:
        return DockerRuntime(params, verbose=self.verbose)

    def _resolve_runtime_params(self, config: DockerRuntimeConfig) -> DockerRuntimeParams:
        return DockerRuntimeParams.from_config(config)

    def _create_builder(self) -> DockerImageBuilder:
        return DockerImageBuilder(verbose=self.verbose)

    def _resolve_build_params(self, config: DockerBuildConfig) -> Dict[str, Any]:
        params = DockerBuildParams.from_config(config)
        return {
            "path": params.context,
            "dockerfile": params.dockerfile,
            "build_args": params.args,
            "labels": params.labels,
            "target": params.target,
            "pull": params.pull,
            "cache_from": params.cache_from,
            "network_mode": params.network,
        }
