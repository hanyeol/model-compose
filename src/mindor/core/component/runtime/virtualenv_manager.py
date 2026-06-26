from __future__ import annotations

from typing import Any, Dict
from mindor.core.foundation.runtime.virtualenv_manager import VirtualEnvRuntimeManager, VirtualEnvRuntimeManagerParams
from mindor.core.component.base import ComponentGlobalConfigs
from mindor.core.foundation.variable.time import parse_duration
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.runtime import VirtualEnvRuntimeConfig

class ComponentVirtualEnvRuntimeManager(VirtualEnvRuntimeManager):
    """Runtime manager for components running inside an isolated virtualenv worker."""

    def __init__(
        self,
        component_id: str,
        config: ComponentConfig,
        global_configs: ComponentGlobalConfigs,
    ):
        self.component_id = component_id
        self.config = config
        self.global_configs = global_configs

        # Convert VirtualEnvRuntimeConfig to VirtualEnvRuntimeManagerParams
        worker_params = self._convert_runtime_config(config.runtime)

        super().__init__(
            worker_id=component_id,
            worker_module="mindor.core.component.runtime.virtualenv_worker",
            worker_params=worker_params,
        )

    @staticmethod
    def _convert_runtime_config(config: VirtualEnvRuntimeConfig) -> VirtualEnvRuntimeManagerParams:
        """Convert DSL VirtualEnvRuntimeConfig to foundation VirtualEnvRuntimeManagerParams"""
        return VirtualEnvRuntimeManagerParams(
            driver=config.driver,
            python=config.python,
            path=config.path,
            env=config.env or {},
            start_timeout=parse_duration(config.start_timeout),
            stop_timeout=parse_duration(config.stop_timeout)
        )

    async def run(self, action_id: str, run_id: str, input_data: Dict[str, Any]) -> Any:
        return await self.execute({
            "action_id": action_id,
            "run_id": run_id,
            "input": input_data,
        })

    def _build_init_payload(self) -> Dict[str, Any]:
        return {
            "component_id": self.component_id,
            "component_config": self.config.model_dump(mode="json"),
            "global_configs": self.global_configs.model_dump(mode="json"),
        }
