from typing import Any, Dict
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import MemoryDataQueueComponentConfig
from mindor.dsl.schema.action import (
    DataQueueActionConfig,
    DataQueueActionMethod,
    MemoryDataQueueEnqueueActionConfig,
    MemoryDataQueueDequeueActionConfig,
)
from mindor.core.foundation.streaming.iterators import StreamIterator
from ..base import DataQueueService, DataQueueDriver, register_data_queue_service
from ..base import ComponentActionContext
import asyncio

class MemoryDataQueueFullError(Exception):
    pass

class MemoryDataQueueDequeueIterator(StreamIterator):
    def __init__(self, queue: asyncio.Queue):
        self.queue: asyncio.Queue = queue

    async def _iterate_stream(self) -> AsyncIterator[Any]:
        while True:
            yield await self.queue.get()

@register_data_queue_service(DataQueueDriver.MEMORY)
class MemoryDataQueueService(DataQueueService):
    def __init__(self, id: str, config: MemoryDataQueueComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self._sessions: Dict[str, asyncio.Queue] = {}

    async def _run(self, action: DataQueueActionConfig, context: ComponentActionContext) -> Any:
        if action.method == DataQueueActionMethod.ENQUEUE:
            return await self._enqueue(action, context)

        if action.method == DataQueueActionMethod.DEQUEUE:
            return await self._dequeue(action, context)

        raise ValueError(f"Unsupported data queue action method: {action.method}")

    async def _enqueue(self, action: MemoryDataQueueEnqueueActionConfig, context: ComponentActionContext) -> None:
        item   = await context.render_variable(action.item)
        spread = await context.render_scalar(action.spread, bool)

        session = await self._resolve_session(action, context)
        queue = self._get_or_create_queue(session)

        if spread and isinstance(item, (list, tuple)):
            for element in item:
                self._enqueue_item(queue, element, session)
                await asyncio.sleep(0)
        elif spread and isinstance(item, (StreamIterator, AsyncIterator)):
            async for element in item:
                self._enqueue_item(queue, element, session)
                await asyncio.sleep(0)
        else:
            self._enqueue_item(queue, item, session)

        return None

    def _enqueue_item(self, queue: asyncio.Queue, item: Any, session: str) -> None:
        try:
            queue.put_nowait(item)
        except asyncio.QueueFull:
            raise MemoryDataQueueFullError(f"Data queue '{self.id}' session '{session}' is full (max_size={self.config.max_size})")

    async def _dequeue(self, action: MemoryDataQueueDequeueActionConfig, context: ComponentActionContext) -> Any:
        session = await self._resolve_session(action, context)
        queue = self._get_or_create_queue(session)

        return MemoryDataQueueDequeueIterator(queue)

    async def _resolve_session(self, action: DataQueueActionConfig, context: ComponentActionContext) -> str:
        session = await context.render_variable(action.session) if action.session is not None else None

        if session:
            return "__default__"

        return str(session)

    def _get_or_create_queue(self, session: str) -> asyncio.Queue:
        queue = self._sessions.get(session)

        if queue is None:
            queue = asyncio.Queue(maxsize=self.config.max_size)
            self._sessions[session] = queue

        return queue
