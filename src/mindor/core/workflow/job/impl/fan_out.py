from __future__ import annotations

from typing import Union, List, Optional, Any
from collections.abc import AsyncIterable, AsyncIterator
from mindor.dsl.schema.job import FanOutJobConfig
from mindor.core.component import ComponentGlobalConfigs
from mindor.core.foundation.streaming.iterators import StreamChunkIterator
from mindor.core.foundation.streaming.resources import StreamResource
from mindor.core.utils.iterators import BatchSourceIterator
from ..base import JobType, RoutingTarget, register_job
from ..context import JobContext
from .common import ComponentRunnerJob
import asyncio

_END_OF_STREAM = object()

class FanOutPump:
    """Broadcast a single async source to N independent branches with bounded backpressure.

    Private helper for the fan-out job. Iterates the source once and pushes each
    chunk to a per-branch bounded queue. When the slowest branch's queue fills,
    the pump blocks so all branches advance at that pace (memory stays bounded).

    The pump task is started eagerly in the constructor (so a running event
    loop is required). It fills each branch's queue up to `buffer_size` and
    then blocks on `put` until a consumer drains one item. If a branch closes
    without consuming, its queue is drained so the pump unblocks. When every
    branch has closed, the pump task is cancelled.
    """
    def __init__(self, source: AsyncIterable[Any], count: int, buffer_size: int = 32):
        self._source = source
        self._count = count
        self._queues: List[asyncio.Queue] = [ asyncio.Queue(maxsize=buffer_size) for _ in range(count) ]
        self._pump_task: asyncio.Task = asyncio.create_task(self._pump())

    def branches(self) -> List[AsyncIterator[Any]]:
        return [ self._iterate_branch(index) for index in range(self._count) ]

    async def _iterate_branch(self, index: int) -> AsyncIterator[Any]:
        queue = self._queues[index]

        try:
            while True:
                item = await queue.get()

                if item is _END_OF_STREAM:
                    return

                if isinstance(item, BaseException):
                    raise item

                yield item
        finally:
            await self._close_branch(index)

    async def _close_branch(self, index: int) -> None:
        queue = self._queues[index]

        self._queues[index] = None

        while not queue.empty():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        if not self._has_alive_branch() and not self._pump_task.done():
            self._pump_task.cancel()

    async def _pump(self) -> None:
        try:
            async for item in self._source:
                if not self._has_alive_branch():
                    return

                await self._broadcast(item)
        except BaseException as e:
            await self._broadcast(e)
            return

        await self._broadcast(_END_OF_STREAM)

    async def _broadcast(self, item: Any) -> None:
        for queue in self._queues:
            if queue is not None:
                await queue.put(item)

    def _has_alive_branch(self) -> bool:
        return any(queue is not None for queue in self._queues)

@register_job(JobType.FAN_OUT)
class FanOutJob(ComponentRunnerJob):
    def __init__(self, id: str, config: FanOutJobConfig, global_configs: ComponentGlobalConfigs):
        super().__init__(id, config, global_configs)

    async def _run(self, context: JobContext) -> Union[Any, RoutingTarget]:
        input       = await context.render_variable(None, self.config.input)
        output      = await context.render_variable(None, self.config.output)
        buffer_size = await context.render_variable(None, self.config.buffer_size)

        await self._started(input)

        input = await self._before_run(context, None, input)

        if isinstance(input, StreamResource):
            if input.copyable():
                branches = input.copy(len(output))
            else:
                sources  = FanOutPump(input, len(output), buffer_size=buffer_size).branches()
                branches = input.tee(sources)
        else:
            async def _fanout_source(source=input):
                async for batch_items in BatchSourceIterator(source, batch_size=1):
                    yield batch_items[0]

            sources = FanOutPump(_fanout_source(), len(output), buffer_size=buffer_size).branches()

            if isinstance(input, StreamChunkIterator):
                branches = [ StreamChunkIterator(source, is_fragmented=input.is_fragmented) for source in sources ]
            else:
                branches = sources

        output = { name: branch for name, branch in zip(output, branches) }
        output = await self._after_run(context, None, input, output)

        return output
