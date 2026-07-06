from __future__ import annotations

from typing import Any, Dict, Optional
from mindor.dsl.schema.containers.docker import DockerBuildConfig
from mindor.dsl.schema.runtime import DockerRuntimeConfig
from mindor.core.foundation.containers.docker import DockerContainerRunner, DockerImageBuilder, DockerContainerOptions
from mindor.core.foundation.variable.time import parse_duration
from .common import ContainerRuntimeBackend

class DockerRuntime(DockerContainerRunner):
    config: DockerRuntimeConfig

    def __init__(
        self,
        config: DockerRuntimeConfig,
        options: Optional[DockerContainerOptions] = None,
        verbose: bool = False,
    ):
        super().__init__(config, options=options, verbose=verbose)

    async def stop(self) -> None:
        await super().stop(timeout=parse_duration(self.config.stop_timeout))

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
