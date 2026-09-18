from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Dict, List, Any
from mindor.dsl.schema.controller import ControllerQueueConfig, ControllerQueueDriverType
from mindor.core.workflow.interrupt import InterruptHandler
from .base import CommonControllerQueueService, ControllerQueueDriverRegistry

class ControllerQueueService:
    def __init__(self, config: ControllerQueueConfig):
        self.config = config
        self.driver: CommonControllerQueueService = self._create_driver(config.driver)

    def _create_driver(self, driver: ControllerQueueDriverType) -> CommonControllerQueueService:
        if not ControllerQueueDriverRegistry:
            from . import drivers
        try:
            return ControllerQueueDriverRegistry[driver](self.config)
        except KeyError:
            raise ValueError(f"Unsupported controller queue driver: {driver}")

    def get_declared_requirements(self) -> List[str]:
        return list(self.driver.get_declared_requirements())

    async def start(self) -> None:
        await self.driver.start()

    async def stop(self) -> None:
        await self.driver.stop()

    async def dispatch(
        self,
        task_id: str,
        workflow_id: str,
        input: Dict[str, Any],
        interrupt_handler: InterruptHandler
    ) -> Any:
        return await self.driver.dispatch(task_id, workflow_id, input, interrupt_handler)
