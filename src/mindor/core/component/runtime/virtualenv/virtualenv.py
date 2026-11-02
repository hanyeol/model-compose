from __future__ import annotations

from typing import Any, Optional, Union
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.runtime import VirtualEnvRuntimeConfig
from mindor.core.component.base import ComponentGlobalConfigs
from mindor.core.component.runtime.common import ComponentRuntimeManager, ComponentRuntimeProxy
from mindor.core.foundation.variable.time import parse_time
from mindor.core.runtime.virtualenv import LocalVirtualEnvRuntime, RemoteVirtualEnvRuntime
from mindor.core.utils.channels.ssh_exec import SshExecChannel
from mindor.core.utils.channels.subprocess_pipe import SubprocessPipeChannel
from .local import ComponentLocalVirtualEnvRuntimeProxy
from .remote import ComponentRemoteVirtualEnvRuntimeProxy
import os

_LOCAL_WORKER_MODULE  = "mindor.core.component.runtime.virtualenv.local"
_REMOTE_WORKER_MODULE = "mindor.core.component.runtime.virtualenv.remote"

class ComponentVirtualEnvRuntimeManager(ComponentRuntimeManager):
    """Manager: provisions and runs a venv-isolated worker.

    Dispatches between two transports based on ``config.remote``:
    - ``None`` → ``LocalVirtualEnvRuntime`` (local venv + inherited pipe fds).
    - set     → ``RemoteVirtualEnvRuntime`` over SSH, running
                 ``python -m mindor.core.component.runtime.virtualenv.remote``
                 on the remote host.
    """
    def __init__(
        self,
        component_id: str,
        component_config: ComponentConfig,
        global_configs: ComponentGlobalConfigs,
    ):
        super().__init__(component_id, component_config, global_configs)

        self._runtime_config: VirtualEnvRuntimeConfig = component_config.runtime
        self._start_timeout = parse_time(self._runtime_config.start_timeout) if self._runtime_config.start_timeout is not None else None
        self._stop_timeout  = parse_time(self._runtime_config.stop_timeout) if self._runtime_config.stop_timeout is not None else None

        self._runtime: Optional[Union[LocalVirtualEnvRuntime, RemoteVirtualEnvRuntime]] = None

    async def _setup(self) -> None:
        # The venv itself + `mindor` + user requirements are the slow,
        # cacheable half of this runtime. Materialize them at setup() so a
        # later start() only has to spawn the worker.
        if self._runtime_config.remote is not None:
            await self._setup_remote()
            return

        await self._setup_local()

    async def _teardown(self) -> None:
        # The venv is a reusable asset — leave it for the next setup. Only
        # drop our in-memory handle so a fresh setup() rebuilds the view.
        self._runtime = None

    async def _launch(self) -> Any:
        if isinstance(self._runtime, RemoteVirtualEnvRuntime):
            return await self._launch_remote()

        return await self._launch_local()

    async def _shutdown(self, channel: Any) -> None:
        if isinstance(channel, SubprocessPipeChannel):
            try:
                channel.close()
            except Exception:
                pass

        if self._runtime is not None:
            await self._runtime.stop()

    def _create_proxy(self, channel: Any) -> ComponentRuntimeProxy:
        if isinstance(self._runtime, RemoteVirtualEnvRuntime):
            proxy: ComponentRuntimeProxy = ComponentRemoteVirtualEnvRuntimeProxy(
                self.worker_id,
                self.component_config,
                self.global_configs,
                channel,
            )
        else:
            proxy = ComponentLocalVirtualEnvRuntimeProxy(
                self.worker_id,
                self.component_config,
                self.global_configs,
                channel,
            )

        proxy._start_timeout = self._start_timeout
        proxy._stop_timeout  = self._stop_timeout

        return proxy

    async def _setup_local(self) -> None:
        self._runtime = LocalVirtualEnvRuntime(
            worker_id=self.worker_id,
            worker_module=_LOCAL_WORKER_MODULE,
            config=self._runtime_config,
        )

        async with self._runtime.bootstrap_lock():
            await self._runtime.create_venv()
            await self._runtime.install_mindor_source()
            await self._runtime.install_requirements()

    async def _setup_remote(self) -> None:
        self._runtime = RemoteVirtualEnvRuntime(
            remote_config=self._runtime_config.remote,
            worker_id=self.worker_id,
            worker_module=_REMOTE_WORKER_MODULE,
            config=self._runtime_config,
        )

        await self._runtime.establish()

        async with self._runtime.bootstrap_lock():
            await self._runtime.create_venv()
            await self._runtime.install_mindor_source()
            await self._runtime.install_requirements()

    async def _launch_local(self) -> SubprocessPipeChannel:
        # Create the pipe pair before spawning so we can hand the child its fds.
        # The Runtime hides whether inheritance happens via POSIX pass_fds or
        # Windows STARTUPINFO.handle_list — we just pass the two fds.
        request_r,  request_w  = os.pipe()
        response_r, response_w = os.pipe()

        try:
            await self._runtime.start(request_fd=request_r, response_fd=response_w)
        finally:
            # The child duplicates its fds; the parent should hold only its own ends.
            os.close(request_r)
            os.close(response_w)

        # Parent uses: read responses on response_r, write requests on request_w.
        return SubprocessPipeChannel(request_fd=response_r, response_fd=request_w)

    async def _launch_remote(self) -> SshExecChannel:
        return await self._runtime.start()
