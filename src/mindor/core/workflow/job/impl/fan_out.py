from __future__ import annotations

from typing import Union, List, Optional, Any
from collections.abc import AsyncIterable, AsyncIterator
from mindor.dsl.schema.job import FanOutJobConfig
from mindor.core.component import ComponentGlobalConfigs
from mindor.core.foundation.streaming.iterators import StreamChunkIterator
from mindor.core.foundation.streaming.resources import StreamResource
from mindor.core.utils.files import get_temporary_path
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.logger import logging
from ..base import JobType, RoutingTarget, register_job
from ..context import JobContext
from .common import ComponentRunnerJob
import asyncio, aiofiles, os

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

class FanOutSpooler:
    """Spool a StreamResource onto a tempfile so N branches can read it independently.

    Helper for the fan-out job's `spool: true` mode. A background writer task
    drains the source stream into a tempfile while branch readers seek/read
    from the same file. Readers block on `_written_event` when they catch up
    to the writer; the writer sets `_write_done` when the source is exhausted.
    The tempfile is deleted once every branch has released its handle.
    """
    def __init__(self, source: StreamResource):
        self._source = source
        self._path: str = get_temporary_path(reserve_file=True)
        self._bytes_written: int = 0
        self._written_event: asyncio.Event = asyncio.Event()
        self._write_done: bool = False
        self._write_error: Optional[BaseException] = None
        self._ref_count: int = 0
        self._writer_task: asyncio.Task = asyncio.create_task(self._write())

    def acquire(self) -> None:
        self._ref_count += 1

    async def release(self) -> None:
        self._ref_count -= 1

        if self._ref_count > 0:
            return

        if not self._writer_task.done():
            self._writer_task.cancel()

        try:
            await self._source.close()
        except Exception:
            pass

        try:
            os.remove(self._path)
        except OSError:
            pass

    async def wait_for(self, offset: int) -> None:
        """Block until at least `offset` bytes are written or the writer finishes."""
        while offset > self._bytes_written and not self._write_done:
            if self._write_error is not None:
                raise self._write_error

            self._written_event.clear()
            await self._written_event.wait()

        if self._write_error is not None:
            raise self._write_error

    @property
    def path(self) -> str:
        return self._path

    @property
    def bytes_written(self) -> int:
        return self._bytes_written

    @property
    def write_done(self) -> bool:
        return self._write_done

    async def _write(self) -> None:
        try:
            async with aiofiles.open(self._path, "wb") as f:
                async for chunk in self._source:
                    await f.write(chunk)
                    self._bytes_written += len(chunk)
                    self._written_event.set()
        except BaseException as e:
            self._write_error = e
        finally:
            self._write_done = True
            self._written_event.set()

class SpooledStreamResource(StreamResource):
    """StreamResource backed by a fan-out spooler's tempfile.

    Each branch holds its own instance; iteration opens a fresh file handle,
    so branches can read at independent paces. Closing releases the spooler's
    reference count — the tempfile is deleted when the last branch closes.
    """
    def __init__(
        self,
        spooler: FanOutSpooler,
        content_type: Optional[str],
        filename: Optional[str],
        size: Optional[int],
        chunk_size: int = 65536,
    ):
        super().__init__(content_type, filename, size=size)

        self._spooler: FanOutSpooler = spooler
        self._chunk_size: int = chunk_size
        self._closed: bool = False

        spooler.acquire()

    def copyable(self) -> bool:
        return True

    def copy(self, count: int) -> List[SpooledStreamResource]:
        return [
            SpooledStreamResource(self._spooler, self.content_type, self.filename, self.size, self._chunk_size)
            for _ in range(count)
        ]

    async def close(self) -> None:
        if self._closed:
            return

        self._closed = True
        await self._spooler.release()

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        offset = 0

        async with aiofiles.open(self._spooler.path, "rb") as f:
            while True:
                await self._spooler.wait_for(offset + self._chunk_size)

                await f.seek(offset)
                chunk = await f.read(self._chunk_size)

                if not chunk:
                    if self._spooler.write_done:
                        return
                    continue

                offset += len(chunk)
                yield chunk

@register_job(JobType.FAN_OUT)
class FanOutJob(ComponentRunnerJob):
    def __init__(self, id: str, config: FanOutJobConfig, global_configs: ComponentGlobalConfigs):
        super().__init__(id, config, global_configs)

    async def _run(self, context: JobContext) -> Union[Any, RoutingTarget]:
        input       = await context.render_variable(None, self.config.input)
        output      = await context.render_variable(None, self.config.output)
        buffer_size = await context.render_variable(None, self.config.buffer_size)
        spool       = await context.render_variable(None, self.config.spool)

        await self._started(input)

        input = await self._before_run(context, None, input)

        if isinstance(input, StreamResource):
            if input.copyable():
                branches = input.copy(len(output))
            else:
                if spool:
                    spooler = FanOutSpooler(input)
                    branches = [
                        SpooledStreamResource(spooler, input.content_type, input.filename, input.size)
                        for _ in range(len(output))
                    ]
                else:
                    sources  = FanOutPump(input, len(output), buffer_size=buffer_size).branches()
                    branches = input.tee(sources)
        else:
            if spool:
                logging.warning(
                    "[task-%s] Job '%s:%s' ignoring 'spool: true' — only valid for a single StreamResource input.",
                    context.workflow.task_id, self.id, context.workflow.workflow_id,
                )

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
