from __future__ import annotations

from typing import Any, Dict, Optional
from mindor.dsl.schema.containers.apple_container import AppleContainerBuildConfig
from mindor.dsl.schema.runtime import AppleContainerRuntimeConfig
from mindor.core.foundation.containers.apple_container import (
    AppleContainerOptions,
    AppleContainerRunner,
    AppleContainerImageBuilder,
)
from mindor.core.foundation.variable.time import parse_duration
from .common import ContainerRuntimeBackend

class AppleContainerRuntime(AppleContainerRunner):
    config: AppleContainerRuntimeConfig

    def __init__(
        self,
        config: AppleContainerRuntimeConfig,
        options: Optional[AppleContainerOptions] = None,
        verbose: bool = False,
    ):
        super().__init__(config, options=options, verbose=verbose)

    async def stop(self) -> None:
        await super().stop(timeout=parse_duration(self.config.stop_timeout))

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
