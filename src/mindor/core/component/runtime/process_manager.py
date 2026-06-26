from typing import Any, Dict
from mindor.core.foundation.runtime import ProcessRuntimeManager
from mindor.core.foundation.runtime.process_manager import ProcessRuntimeManagerParams
from mindor.core.component.base import ComponentGlobalConfigs
from mindor.core.component.runtime.process_worker import ComponentProcessRuntimeWorker
from mindor.core.foundation.variable.time import parse_duration
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.runtime import ProcessRuntimeConfig
from multiprocessing import Queue
from functools import partial

class ComponentProcessRuntimeManager(ProcessRuntimeManager):
    """Process runtime manager for components"""

    def __init__(
        self,
        component_id: str,
        config: ComponentConfig,
        global_configs: ComponentGlobalConfigs
    ):
        self.config = config
        self.global_configs = global_configs

        # Create a partial function that's picklable
        # Pass config and global_configs directly to the factory
        worker_factory = partial(
            self._component_worker_factory,
            config=config,
            global_configs=global_configs
        )

        # Convert ProcessRuntimeConfig to ProcessRuntimeManagerParams
        worker_params = self._convert_runtime_config(config.runtime)

        super().__init__(component_id, worker_factory, worker_params)

    @staticmethod
    def _convert_runtime_config(config: ProcessRuntimeConfig) -> ProcessRuntimeManagerParams:
        """Convert DSL ProcessRuntimeConfig to foundation ProcessRuntimeManagerParams"""
        return ProcessRuntimeManagerParams(
            env=config.env,
            start_timeout=parse_duration(config.start_timeout),
            stop_timeout=parse_duration(config.stop_timeout)
        )

    @staticmethod
    def _component_worker_factory(
        worker_id: str,
        request_queue: Queue,
        response_queue: Queue,
        config: ComponentConfig,
        global_configs: ComponentGlobalConfigs
    ) -> ComponentProcessRuntimeWorker:
        return ComponentProcessRuntimeWorker(
            worker_id,
            config,
            global_configs,
            request_queue,
            response_queue
        )

    async def run(
        self,
        action_id: str,
        run_id: str,
        input_data: Dict[str, Any]
    ) -> Any:
        """Execute component action"""
        return await self.execute({
            "action_id": action_id,
            "run_id": run_id,
            "input": input_data
        })
