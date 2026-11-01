from __future__ import annotations

from typing import Optional, Tuple
from mindor.dsl.schema.component import ComponentConfig
from mindor.core.component.base import ComponentGlobalConfigs
from mindor.core.component.runtime.common import ComponentRuntimeProxy, ComponentRuntimeWorker
from mindor.core.logger import logging
import asyncio, multiprocessing

# Match the spawn context used by LocalProcessRuntime so queue handles are picklable
# by the child (fork-context queues cannot be handed to a spawn-context child).
Queue = multiprocessing.get_context("spawn").Queue

class ComponentLocalProcessRuntimeWorker(ComponentRuntimeWorker):
    """Local worker: runs inside a spawn-context subprocess and bridges IPC
    over a `multiprocessing.Queue` pair."""
    def __init__(
        self,
        component_id: str,
        component_config: ComponentConfig,
        global_configs: ComponentGlobalConfigs,
        request_queue: Queue,
        response_queue: Queue,
    ):
        super().__init__(component_id, component_config, global_configs)

        self.request_queue = request_queue
        self.response_queue = response_queue

    async def _start(self) -> None:
        await super()._start()

        logging.info("process: component '%s' started in subprocess", self.worker_id)

    async def _send_message(self, message: bytes) -> None:
        await self._loop.run_in_executor(None, self.response_queue.put, message)

    async def _recv_message(self) -> Optional[bytes]:
        return await self._loop.run_in_executor(None, self.request_queue.get)

    def _close_transport(self) -> None:
        # Queue objects do not need explicit close from the worker side; the
        # parent owns the queue lifecycle.
        pass

class ComponentLocalProcessRuntimeProxy(ComponentRuntimeProxy):
    """multiprocessing.Queue-based IPC proxy.

    The channel is a `(request_queue, response_queue)` tuple. Parent writes
    RUN into request_queue and reads RESULT from response_queue.
    """
    channel: Tuple[Queue, Queue]

    async def _stop(self) -> None:
        await super()._stop()

        # Unblock the executor thread parked in _recv_message (Queue.get is blocking).
        _, response_queue = self.channel
        response_queue.put(None)

    async def _send_start_message(self) -> None:
        # multiprocessing `spawn` pickled the component config into the
        # worker's args; no START message on the wire.
        pass

    async def _send_message(self, message: bytes) -> None:
        request_queue, _ = self.channel
        await self._loop.run_in_executor(None, request_queue.put, message)

    async def _recv_message(self) -> Optional[bytes]:
        _, response_queue = self.channel
        return await self._loop.run_in_executor(None, response_queue.get)

def run_local_worker(
    worker_id: str,
    component_config: ComponentConfig,
    global_configs: ComponentGlobalConfigs,
    request_queue: Queue,
    response_queue: Queue,
) -> None:
    """Local subprocess entry point. Top-level so it can be pickled for `spawn` start."""
    worker = ComponentLocalProcessRuntimeWorker(
        worker_id,
        component_config,
        global_configs,
        request_queue,
        response_queue,
    )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(worker.run())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()
