from typing import Optional, Tuple
from multiprocessing import Queue
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.runtime import ProcessRuntimeConfig
from mindor.core.component.base import ComponentGlobalConfigs
from mindor.core.component.runtime.common import (
    ComponentRuntimeLauncher,
    ComponentRuntimeProxy,
    ComponentRuntimeWorker,
)
from mindor.core.foundation.variable.time import parse_duration
from mindor.core.logger import logging
from mindor.core.runtime.process import ProcessRuntime, ProcessRuntimeParams
import asyncio


class ComponentProcessRuntimeWorker(ComponentRuntimeWorker):
    """Worker that runs inside the child process and hosts an embedded component."""
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
        logging.info(f"Component {self.worker_id} started in subprocess")

    async def _send_message(self, message: bytes) -> None:
        await self._loop.run_in_executor(None, self.response_queue.put, message)

    async def _recv_message(self) -> Optional[bytes]:
        return await self._loop.run_in_executor(None, self.request_queue.get)

    def _close_transport(self) -> None:
        # Queue objects do not need explicit close from the worker side; the
        # parent owns the queue lifecycle.
        pass

class ComponentProcessRuntimeProxy(ComponentRuntimeProxy):
    """multiprocessing.Queue-based IPC proxy.

    The channel is a `(request_queue, response_queue)` tuple. Parent writes
    RUN into request_queue and reads RESULT from response_queue.
    """
    _channel: Tuple[Queue, Queue]

    async def _stop(self) -> None:
        await super()._stop()

        # Unblock the executor thread parked in _recv_message (Queue.get is blocking).
        _, response_queue = self._channel
        response_queue.put(None)

    async def _send_start_message(self) -> None:
        # multiprocessing `spawn` pickled the component config into the
        # worker's args; no START message on the wire.
        pass

    async def _send_message(self, message: bytes) -> None:
        request_queue, _ = self._channel
        await self._loop.run_in_executor(None, request_queue.put, message)

    async def _recv_message(self) -> Optional[bytes]:
        _, response_queue = self._channel
        return await self._loop.run_in_executor(None, response_queue.get)


class ComponentProcessRuntimeLauncher(ComponentRuntimeLauncher):
    """Launcher: spawns a `ProcessRuntime` child and wraps its queue pair in
    a `ComponentProcessRuntimeProxy`.
    """
    def __init__(
        self,
        component_id: str,
        component_config: ComponentConfig,
        global_configs: ComponentGlobalConfigs,
    ):
        super().__init__(component_id, component_config, global_configs)

        self.params = self._resolve_runtime_params(component_config.runtime)

        self._request_queue: Optional[Queue] = None
        self._response_queue: Optional[Queue] = None
        self._runtime: Optional[ProcessRuntime] = None

    async def _prepare_channel(self) -> Tuple[Queue, Queue]:
        self._request_queue = Queue()
        self._response_queue = Queue()

        self._runtime = ProcessRuntime(
            target=self._run_worker,
            args=(
                self.worker_id,
                self.component_config,
                self.global_configs,
                self._request_queue,
                self._response_queue,
            ),
            params=self.params,
        )
        await self._runtime.start()

        return (self._request_queue, self._response_queue)

    def _create_proxy(self, channel: Tuple[Queue, Queue]) -> ComponentProcessRuntimeProxy:
        proxy = ComponentProcessRuntimeProxy(
            self.worker_id,
            self.component_config,
            self.global_configs,
            channel,
        )
        proxy._start_timeout = self.params.start_timeout
        proxy._stop_timeout = self.params.stop_timeout
        return proxy

    async def _teardown_runtime(self) -> None:
        if self._runtime is not None:
            await self._runtime.stop()
            self._runtime = None

    def _close_channel(self, channel: Tuple[Queue, Queue]) -> None:
        # Queue objects have no `close()` we need; runtime teardown handles
        # child exit. Nothing to do here.
        pass

    def _resolve_runtime_params(self, config: ProcessRuntimeConfig) -> ProcessRuntimeParams:
        return ProcessRuntimeParams(
            env=config.env,
            start_timeout=parse_duration(config.start_timeout),
            stop_timeout=parse_duration(config.stop_timeout),
        )

    @staticmethod
    def _run_worker(
        worker_id: str,
        component_config: ComponentConfig,
        global_configs: ComponentGlobalConfigs,
        request_queue: Queue,
        response_queue: Queue,
    ) -> None:
        """Subprocess entry point. Static so it can be pickled for `spawn` start."""
        worker = ComponentProcessRuntimeWorker(
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
