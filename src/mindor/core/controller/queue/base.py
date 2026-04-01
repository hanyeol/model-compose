from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Dict, Any, Callable, Awaitable
from abc import abstractmethod
from mindor.dsl.schema.controller import ControllerQueueDriver
from mindor.dsl.schema.controller.queue.impl.common import CommonControllerQueueConfig
from mindor.core.foundation import AsyncService
from mindor.core.workflow.interrupt import InterruptHandler, InterruptPoint
import asyncio

InterruptCallback = Callable[[Dict[str, Any]], Awaitable[Any]]

class CommonControllerQueueService(AsyncService):
    def __init__(self, config: CommonControllerQueueConfig):
        super().__init__(daemon=False)
        self.config = config

    async def dispatch(
        self,
        task_id: str,
        workflow_id: str,
        input: Dict[str, Any],
        interrupt_handler: InterruptHandler
    ) -> Any:
        async def on_interrupt(data: Dict[str, Any]) -> Any:
            point = InterruptPoint(
                task_id=task_id,
                job_id=data.get("job_id", ""),
                phase=data.get("phase", "before"),
                message=data.get("message"),
                metadata=data.get("metadata"),
                future=asyncio.get_event_loop().create_future(),
            )
            await interrupt_handler.interrupt(point)
            return await point.future

        return await self._dispatch(task_id, workflow_id, input, on_interrupt)

    @abstractmethod
    async def _dispatch(
        self,
        task_id: str,
        workflow_id: str,
        input: Dict[str, Any],
        on_interrupt: InterruptCallback
    ) -> Any:
        pass

def register_controller_queue_service(driver: ControllerQueueDriver):
    def decorator(cls: Type[CommonControllerQueueService]) -> Type[CommonControllerQueueService]:
        ControllerQueueServiceRegistry[driver] = cls
        return cls
    return decorator

ControllerQueueServiceRegistry: Dict[ControllerQueueDriver, Type[CommonControllerQueueService]] = {}
