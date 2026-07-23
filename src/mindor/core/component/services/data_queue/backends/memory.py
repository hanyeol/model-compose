from typing import Any, Dict
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import MemoryDataQueueComponentConfig
from mindor.dsl.schema.action import (
    DataQueueActionConfig,
    DataQueueActionMethod,
    MemoryDataQueuePublishActionConfig,
    MemoryDataQueueConsumeActionConfig,
)
from mindor.core.foundation.streaming.iterators import StreamIterator
from ..base import DataQueueService, DataQueueDriver, register_data_queue_service
from ..base import ComponentActionContext
import asyncio

DEFAULT_SESSION = "__default__"

class MemoryDataQueueFullError(Exception):
    pass

class MemoryDataQueueConsumeIterator(StreamIterator):
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
        if action.method == DataQueueActionMethod.PUBLISH:
            return await self._publish(action, context)

        if action.method == DataQueueActionMethod.CONSUME:
            return await self._consume(action, context)

        raise ValueError(f"Unsupported data queue action method: {action.method}")

    async def _publish(self, action: MemoryDataQueuePublishActionConfig, context: ComponentActionContext) -> None:
        session = await self._resolve_session(action, context)
        queue = self._get_or_create_queue(session)

        try:
            queue.put_nowait(context.input)
        except asyncio.QueueFull:
            raise MemoryDataQueueFullError(
                f"Data queue '{self.id}' session '{session}' is full (max_size={self.config.max_size})"
            )

        return None

    async def _consume(self, action: MemoryDataQueueConsumeActionConfig, context: ComponentActionContext) -> Any:
        session = await self._resolve_session(action, context)
        queue = self._get_or_create_queue(session)

        return MemoryDataQueueConsumeIterator(queue)

    async def _resolve_session(self, action: DataQueueActionConfig, context: ComponentActionContext) -> str:
        if action.session is None:
            return DEFAULT_SESSION

        rendered = await context.render_variable(action.session)
        if rendered is None or rendered == "":
            return DEFAULT_SESSION

        return str(rendered)

    def _get_or_create_queue(self, session: str) -> asyncio.Queue:
        queue = self._sessions.get(session)
        if queue is None:
            queue = asyncio.Queue(maxsize=self.config.max_size)
            self._sessions[session] = queue
        return queue
