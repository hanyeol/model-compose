from typing import Any, Dict
from mindor.core.foundation import ProcessRuntimeManager
from mindor.core.foundation.process_worker import ProcessWorkerParams
from mindor.core.component.base import ComponentGlobalConfigs
from mindor.core.component.runtime.process_worker import ComponentProcessWorker
from mindor.core.utils.time import parse_duration
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
        if not isinstance(config.runtime, ProcessRuntimeConfig):
            raise ValueError("ComponentProcessRuntimeManager requires ProcessRuntimeConfig")

        self.config = config
        self.global_configs = global_configs

        # Create a partial function that's picklable
        # Pass config and global_configs directly to the factory
        worker_factory = partial(
            self._component_worker_factory,
            config=config,
            global_configs=global_configs
        )

        # Convert ProcessRuntimeConfig to ProcessWorkerParams
        worker_params = self._convert_runtime_config(config.runtime)

        super().__init__(
            worker_id=component_id,
            worker_factory=worker_factory,
            worker_params=worker_params
        )

    @staticmethod
    def _convert_runtime_config(config: ProcessRuntimeConfig) -> ProcessWorkerParams:
        """Convert DSL ProcessRuntimeConfig to foundation ProcessWorkerParams"""
        return ProcessWorkerParams(
            env=config.env,
            start_timeout=parse_duration(config.start_timeout).total_seconds(),
            stop_timeout=parse_duration(config.stop_timeout).total_seconds()
        )

    def _component_worker_factory(
        self,
        worker_id: str,
        request_queue: Queue,
        response_queue: Queue,
        config: ComponentConfig,
        global_configs: ComponentGlobalConfigs
    ) -> ComponentProcessWorker:
        """Instance factory method for ComponentProcessWorker

        This function is picklable and receives config directly as parameters.
        """
        return ComponentProcessWorker(
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
