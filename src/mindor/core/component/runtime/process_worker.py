from typing import Any, Dict
from mindor.core.foundation import ProcessWorker
from mindor.core.component.base import ComponentGlobalConfigs
from mindor.core.component.component import create_component
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.runtime import EmbeddedRuntimeConfig
from mindor.core.logger import logging
from multiprocessing import Queue

class ComponentProcessWorker(ProcessWorker):
    """Worker for running components in separate processes"""

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

    async def _initialize(self) -> None:
        """Initialize and start the component"""
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

    async def _execute_task(self, payload: Dict[str, Any]) -> Any:
        """Execute component action"""
        action_id = payload["action_id"]
        run_id = payload["run_id"]
        input_data = payload["input"]

        return await self.component.run(action_id, run_id, input_data)

    async def _cleanup(self) -> None:
        """Clean up the component"""
        if self.component:
            await self.component.stop()
            await self.component.teardown()
