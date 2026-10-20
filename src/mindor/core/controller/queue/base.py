from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Optional, Dict, List, Any, Callable, Awaitable
from abc import abstractmethod
from mindor.dsl.schema.controller import ControllerQueueDriverType
from mindor.dsl.schema.controller.queue.impl.common import CommonControllerQueueConfig
from mindor.core.foundation import AsyncService
from mindor.core.workflow.interrupt import InterruptHandler, InterruptPoint
import asyncio

# The queue dispatcher receives a batched list of interrupt dicts and returns
# a `{point.id: answer}` dict.
InterruptCallback = Callable[[List[Dict[str, Any]]], Awaitable[Dict[str, Any]]]

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
        async def _on_interrupt(items: List[Dict[str, Any]]) -> Dict[str, Any]:
            # Each remote interrupt becomes a local pending point; running them
            # concurrently lets `interrupt()` register-then-await while the
            # Runner's quiescence detector observes them one by one and
            # eventually flushes the batch to the controller callback.
            points: List[InterruptPoint] = [
                InterruptPoint(
                    id=item["id"],
                    task_id=task_id,
                    job_id=item.get("job_id", ""),
                    run_id=item.get("run_id"),
                    phase=item.get("phase", "before"),
                    message=item.get("message"),
                    metadata=item.get("metadata"),
                    future=asyncio.get_event_loop().create_future(),
                )
                for item in items
            ]

            async def _await_point(point: InterruptPoint) -> tuple[str, Any]:
                answer = await interrupt_handler.interrupt(point)
                return point.id, answer

            results = await asyncio.gather(*[ _await_point(point) for point in points ])

            return dict(results)

        return await self._dispatch(task_id, workflow_id, input, _on_interrupt)

    async def cancel(self, task_id: str) -> None:
        await self._cancel(task_id)

    @abstractmethod
    async def _dispatch(
        self,
        task_id: str,
        workflow_id: str,
        input: Dict[str, Any],
        on_interrupt: InterruptCallback
    ) -> Any:
        pass

    @abstractmethod
    async def _cancel(self, task_id: str) -> None:
        pass

def register_controller_queue_driver(driver: ControllerQueueDriverType):
    def decorator(cls: Type[CommonControllerQueueService]) -> Type[CommonControllerQueueService]:
        ControllerQueueDriverRegistry[driver] = cls
        return cls
    return decorator

ControllerQueueDriverRegistry: Dict[ControllerQueueDriverType, Type[CommonControllerQueueService]] = {}
