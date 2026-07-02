from __future__ import annotations

from typing import Any, Dict, Optional
from dataclasses import dataclass
from mindor.dsl.schema.containers.apple_container import AppleContainerBuildConfig
from mindor.dsl.schema.runtime import AppleContainerRuntimeConfig
from mindor.core.foundation.containers.apple_container import (
    AppleContainerParams,
    AppleContainerRunner,
    AppleContainerImageBuilder,
)
from mindor.core.foundation.variable.time import parse_duration
from .common import ContainerRuntimeBackend

@dataclass
class AppleContainerRuntimeParams(AppleContainerParams):
    start_timeout: Optional[float] = None
    stop_timeout: Optional[float] = None

    @classmethod
    def from_config(cls, config: AppleContainerRuntimeConfig) -> AppleContainerRuntimeParams:
        return cls(
            **AppleContainerParams.from_config(config).__dict__,
            start_timeout=parse_duration(config.start_timeout),
            stop_timeout=parse_duration(config.stop_timeout),
        )

class AppleContainerRuntime(AppleContainerRunner):
    def __init__(self, params: AppleContainerRuntimeParams, verbose: bool = False):
        super().__init__(params, verbose=verbose)

        self.params: AppleContainerRuntimeParams = params

    async def stop(self) -> None:
        await super().stop(timeout=self.params.stop_timeout)

class AppleContainerRuntimeBackend(ContainerRuntimeBackend):
    """Apple Container-backed `ContainerRuntimeBackend`."""
    _runtime_config: AppleContainerRuntimeConfig

    def _create_runtime(self, params: AppleContainerRuntimeParams) -> AppleContainerRuntime:
        return AppleContainerRuntime(params, verbose=self.verbose)

    def _resolve_runtime_params(self) -> AppleContainerRuntimeParams:
        return AppleContainerRuntimeParams.from_config(self._runtime_config)

    def _create_builder(self) -> AppleContainerImageBuilder:
        return AppleContainerImageBuilder(verbose=self.verbose)

    def _resolve_build_params(self, config: AppleContainerBuildConfig) -> Dict[str, Any]:
        return {
            "path": config.context,
            "dockerfile": config.dockerfile,
            "build_args": config.args,
            "target": config.target,
            "labels": config.labels,
            "pull": config.pull,
        }
