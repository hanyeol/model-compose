from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Dict, Any
from mindor.dsl.schema.controller import ControllerQueueConfig, ControllerQueueDriver
from mindor.core.workflow.interrupt import InterruptHandler
from .base import CommonControllerQueueService, ControllerQueueServiceRegistry

class ControllerQueueService:
    def __init__(self, config: ControllerQueueConfig):
        self.config = config
        self.service: CommonControllerQueueService = self._create_service(config.driver)

    def _create_service(self, driver: ControllerQueueDriver) -> CommonControllerQueueService:
        if not ControllerQueueServiceRegistry:
            from . import drivers
        try:
            return ControllerQueueServiceRegistry[driver](self.config)
        except KeyError:
            raise ValueError(f"Unsupported controller queue driver: {driver}")

    async def start(self) -> None:
        await self.service.start()

    async def stop(self) -> None:
        await self.service.stop()

    async def dispatch(self, task_id: str, workflow_id: str, input: Dict[str, Any], interrupt_handler: InterruptHandler) -> Any:
        return await self.service.dispatch(task_id, workflow_id, input, interrupt_handler)
