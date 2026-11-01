from __future__ import annotations

from typing import Optional
from mindor.dsl.schema.component import ComponentConfig
from mindor.core.component.base import ComponentGlobalConfigs
from mindor.core.component.runtime.common import ComponentRuntimeProxy, ComponentRuntimeWorker
from mindor.core.component.runtime.base.ipc_message import IpcStartPayload
from mindor.core.foundation.runtime.ipc_message import IpcMessage, IpcMessageType
from mindor.core.utils.channels.subprocess_pipe import SubprocessPipeChannel
import asyncio, os, sys

class ComponentLocalVirtualEnvRuntimeWorker(ComponentRuntimeWorker):
    """Local venv worker: runs in the venv's python and bridges IPC over
    a ``SubprocessPipeChannel`` whose fds were inherited from the parent."""
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

class ComponentLocalVirtualEnvRuntimeProxy(ComponentRuntimeProxy):
    """SubprocessPipeChannel-based IPC proxy for venv-spawned workers."""
    channel: SubprocessPipeChannel

    async def _send_message(self, message: bytes) -> None:
        await self._loop.run_in_executor(None, self.channel.send, message)

    async def _recv_message(self) -> Optional[bytes]:
        return await self._loop.run_in_executor(None, self.channel.recv)

def main() -> None:
    """Local entrypoint for the venv subprocess spawned by
    ``ComponentVirtualEnvRuntimeManager`` on the host.

    The manager hands the child a pipe pair via ``pass_fds`` (POSIX) or
    ``STARTUPINFO.handle_list`` (Windows) and advertises the fd / handle
    numbers through ``MINDOR_VENV_*`` env vars. This main re-opens them,
    reads the first START IPC message off the pipe, and drives the worker.
    """
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

    worker = ComponentLocalVirtualEnvRuntimeWorker(
        payload.component_id,
        payload.component_config,
        payload.global_configs,
        channel,
    )

    asyncio.run(worker.run())

if __name__ == "__main__":
    main()
