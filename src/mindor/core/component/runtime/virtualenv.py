from __future__ import annotations

from typing import Optional
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.runtime import VirtualEnvRuntimeConfig
from mindor.core.component.base import ComponentGlobalConfigs
from mindor.core.component.runtime.common import ComponentRuntimeManager, ComponentRuntimeProxy, ComponentRuntimeWorker
from mindor.core.foundation.runtime.ipc_message import IpcMessage, IpcMessageType
from mindor.core.component.runtime.base.ipc_message import IpcStartPayload
from mindor.core.foundation.variable.time import parse_time
from mindor.core.foundation.package import mindor as mindor_package
from mindor.core.runtime.virtualenv import VirtualEnvRuntime
from mindor.core.utils.channels.subprocess_pipe import SubprocessPipeChannel
from pathlib import Path
import asyncio, os, sys

class ComponentVirtualEnvRuntimeWorker(ComponentRuntimeWorker):
    """Component-side worker that runs inside the venv interpreter.

    Bridges IPC messages over a `SubprocessPipeChannel`.
    """
    def __init__(
        self,
        component_id: str,
        component_config: ComponentConfig,
        global_configs: ComponentGlobalConfigs,
        channel: SubprocessPipeChannel,
    ):
        super().__init__(component_id, component_config, global_configs)

        self.channel: SubprocessPipeChannel = channel

    async def _send_message(self, message: bytes) -> None:
        await self._loop.run_in_executor(None, self.channel.send, message)

    async def _recv_message(self) -> Optional[bytes]:
        return await self._loop.run_in_executor(None, self.channel.recv)

    def _close_transport(self) -> None:
        self.channel.close()

class ComponentVirtualEnvRuntimeProxy(ComponentRuntimeProxy):
    """SubprocessPipeChannel-based IPC proxy for venv-spawned workers."""
    channel: SubprocessPipeChannel

    async def _send_message(self, message: bytes) -> None:
        await self._loop.run_in_executor(None, self.channel.send, message)

    async def _recv_message(self) -> Optional[bytes]:
        return await self._loop.run_in_executor(None, self.channel.recv)

class ComponentVirtualEnvRuntimeManager(ComponentRuntimeManager):
    """Manager: spawns a `VirtualEnvRuntime` child over a pipe pair and
    wraps the parent's ends in a `ComponentVirtualEnvRuntimeProxy`.
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

        self._runtime: Optional[VirtualEnvRuntime] = None

    async def _setup(self) -> None:
        # The venv itself + `mindor` + user requirements are the slow,
        # cacheable half of this runtime. Materialize them at setup() so a
        # later start() only has to spawn the subprocess.
        self._runtime = VirtualEnvRuntime(
            worker_id=self.worker_id,
            worker_module="mindor.core.component.runtime.virtualenv",
            config=self._runtime_config,
        )

        mindor_root_path = mindor_package.get_root_path()
        runtime_requirements_path = mindor_package.get_requirements_path()
        user_requirements_path = (Path.cwd() / "requirements.txt").resolve()

        async with self._runtime.bootstrap_lock():
            await self._runtime.create_venv()
            await self._runtime.install_source(mindor_root_path)
            await self._runtime.install_requirements([ runtime_requirements_path, user_requirements_path ])

    async def _teardown(self) -> None:
        # The venv on disk is a reusable asset — leave it for the next setup.
        # Only drop our in-memory handle so a fresh setup() rebuilds the view.
        self._runtime = None

    async def _launch(self) -> SubprocessPipeChannel:
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

    async def _shutdown(self, channel: SubprocessPipeChannel) -> None:
        try:
            channel.close()
        except Exception:
            pass

        if self._runtime is not None:
            await self._runtime.stop()

    def _create_proxy(self, channel: SubprocessPipeChannel) -> ComponentVirtualEnvRuntimeProxy:
        proxy = ComponentVirtualEnvRuntimeProxy(
            self.worker_id,
            self.component_config,
            self.global_configs,
            channel,
        )

        proxy._start_timeout = self._start_timeout
        proxy._stop_timeout  = self._stop_timeout

        return proxy

def main() -> None:
    """Entrypoint when launched as `python -m mindor.core.component.runtime.virtualenv`."""
    # Ensure stdout/stderr stay attached to the parent as log channels only;
    # the IPC protocol runs on the dedicated fd pair, not on stdout.
    try:
        sys.stdout.reconfigure(line_buffering=True)
        sys.stderr.reconfigure(line_buffering=True)
    except Exception:
        pass

    try:
        if os.name == "nt":
            # Windows path: parent passed OS handles via STARTUPINFO.handle_list and
            # stored the handle values in MINDOR_VENV_*_HANDLE. Convert back to fds.
            import msvcrt

            request_handle  = int(os.environ["MINDOR_VENV_REQUEST_HANDLE"])
            response_handle = int(os.environ["MINDOR_VENV_RESPONSE_HANDLE"])
            request_fd  = msvcrt.open_osfhandle(request_handle, os.O_RDONLY)
            response_fd = msvcrt.open_osfhandle(response_handle, os.O_WRONLY)
        else:
            request_fd  = int(os.environ["MINDOR_VENV_REQUEST_FD"])
            response_fd = int(os.environ["MINDOR_VENV_RESPONSE_FD"])
    except KeyError as e:
        raise RuntimeError(
            f"Missing IPC file descriptor environment variable: {e}. "
            f"This module must be launched by ComponentVirtualEnvRuntimeManager."
        ) from e

    channel = SubprocessPipeChannel(
        request_fd=request_fd,
        response_fd=response_fd,
    )

    init_data = channel.recv()

    if init_data is None:
        raise RuntimeError("Expected first IPC message of type 'start', got EOF")

    init = IpcMessage.deserialize(init_data)

    if init.type != IpcMessageType.START:
        raise RuntimeError(
            f"Expected first IPC message of type 'start', got: {init.type!r}"
        )

    payload = IpcStartPayload.model_validate(init.payload or {})

    worker = ComponentVirtualEnvRuntimeWorker(
        payload.component_id,
        payload.component_config,
        payload.global_configs,
        channel,
    )

    asyncio.run(worker.run())

if __name__ == "__main__":
    main()
