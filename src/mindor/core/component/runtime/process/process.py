from __future__ import annotations

from typing import Any, Optional, Tuple, Union
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.runtime import ProcessRuntimeConfig
from mindor.core.component.base import ComponentGlobalConfigs
from mindor.core.component.runtime.common import ComponentRuntimeManager, ComponentRuntimeProxy
from mindor.core.foundation.variable.time import parse_time
from mindor.core.runtime.process import LocalProcessRuntime, RemoteProcessRuntime
from mindor.core.utils.channels.ssh_exec import SshExecChannel
from .local import ComponentLocalProcessRuntimeProxy, Queue, run_local_worker
from .remote import ComponentRemoteProcessRuntimeProxy

_REMOTE_WORKER_MODULE = "mindor.core.component.runtime.process"

class ComponentProcessRuntimeManager(ComponentRuntimeManager):
    """Manager: spawns a process worker and bridges IPC to it.

    Dispatches between two transports based on ``config.remote``:
    - ``None`` → ``LocalProcessRuntime`` (multiprocessing spawn + Queue pair).
    - set     → ``RemoteProcessRuntime`` over an SSH exec channel, running
                 ``python -m mindor.core.component.runtime.process`` on the
                 remote host.
    """
    def __init__(
        self,
        component_id: str,
        component_config: ComponentConfig,
        global_configs: ComponentGlobalConfigs,
    ):
        super().__init__(component_id, component_config, global_configs)

        self._runtime_config: ProcessRuntimeConfig = component_config.runtime
        self._start_timeout = parse_time(self._runtime_config.start_timeout) if self._runtime_config.start_timeout is not None else None
        self._stop_timeout  = parse_time(self._runtime_config.stop_timeout) if self._runtime_config.stop_timeout is not None else None

        self._runtime: Optional[Union[LocalProcessRuntime, RemoteProcessRuntime]] = None

    async def _launch(self) -> Any:
        if self._runtime_config.remote is not None:
            return await self._launch_remote()

        return await self._launch_local()

    async def _shutdown(self, channel: Any) -> None:
        if self._runtime is not None:
            await self._runtime.stop()
            self._runtime = None

    def _create_proxy(self, channel: Any) -> ComponentRuntimeProxy:
        if self._runtime_config.remote is not None:
            proxy: ComponentRuntimeProxy = ComponentRemoteProcessRuntimeProxy(
                self.worker_id,
                self.component_config,
                self.global_configs,
                channel,
            )
        else:
            proxy = ComponentLocalProcessRuntimeProxy(
                self.worker_id,
                self.component_config,
                self.global_configs,
                channel,
            )

        proxy._start_timeout = self._start_timeout
        proxy._stop_timeout  = self._stop_timeout

        return proxy

    async def _launch_local(self) -> Tuple[Queue, Queue]:
        request_queue  = Queue()
        response_queue = Queue()

        self._runtime = LocalProcessRuntime(
            entrypoint=run_local_worker,
            args=(
                self.worker_id,
                self.component_config,
                self.global_configs,
                request_queue,
                response_queue,
            ),
            config=self._runtime_config,
        )
        await self._runtime.start()

        return (request_queue, response_queue)

    async def _launch_remote(self) -> SshExecChannel:
        self._runtime = RemoteProcessRuntime(
            remote_config=self._runtime_config.remote,
            worker_module=_REMOTE_WORKER_MODULE,
            config=self._runtime_config,
        )

        return await self._runtime.start()
