from typing import Any, Dict
from mindor.core.runtime.process import (
    ProcessRuntimeManager,
    ProcessRuntimeManagerParams,
    ProcessRuntimeWorker,
)
from mindor.core.component.base import ComponentGlobalConfigs
from mindor.core.component.component import create_component
from mindor.core.foundation.variable.time import parse_duration
from mindor.core.logger import logging
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.runtime import EmbeddedRuntimeConfig, ProcessRuntimeConfig
from multiprocessing import Queue
from functools import partial


class ComponentProcessRuntimeWorker(ProcessRuntimeWorker):
    def __init__(
        self,
        component_id: str,
        config: ComponentConfig,
        global_configs: ComponentGlobalConfigs,
        request_queue: Queue,
        response_queue: Queue
    ):
        super().__init__(component_id, request_queue, response_queue)

        self.config = config
        self.global_configs = global_configs
        self.component = None

    async def _start(self) -> None:
        embedded_config = self.config.model_copy(deep=True)
        embedded_config.runtime = EmbeddedRuntimeConfig(type="embedded")

        self.component = create_component(
            self.worker_id,
            embedded_config,
            self.global_configs,
            daemon=True
        )

        await self.component.setup()
        await self.component.start()

        logging.info(f"Component {self.worker_id} started in subprocess")

    async def _stop(self) -> None:
        if self.component:
            await self.component.stop()
            await self.component.teardown()

    async def _execute_task(self, payload: Dict[str, Any]) -> Any:
        action_id  = payload["action_id"]
        run_id     = payload["run_id"]
        input_data = payload["input"]

        return await self.component.run(action_id, run_id, input_data)


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
