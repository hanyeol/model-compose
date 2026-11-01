from __future__ import annotations

from typing import BinaryIO, Optional
from mindor.dsl.schema.component import ComponentConfig
from mindor.core.component.base import ComponentGlobalConfigs
from mindor.core.component.runtime.common import ComponentRuntimeProxy, ComponentRuntimeWorker
from mindor.core.component.runtime.base.ipc_stdio_channel import stdio_worker_factory
from mindor.core.foundation.runtime.ipc_stdio_channel import IpcStdioChannel
from mindor.core.utils.channels.ssh_exec import SshExecChannel
import struct

# IPC frame prefix shared with IpcMessage: header_len + binary_len (BE u32).
_IPC_FRAME_PREFIX = struct.Struct(">II")
_IPC_FRAME_PREFIX_SIZE = _IPC_FRAME_PREFIX.size

class ComponentRemoteVirtualEnvRuntimeWorker(ComponentRuntimeWorker):
    """Remote venv worker: runs in the remote venv's python under an SSH
    exec channel. Bridges IPC over the stdin/stdout fds that
    ``IpcStdioChannel.setup()`` carved off from fd 0/1 before redirecting
    them to stderr.
    """
    def __init__(
        self,
        component_id: str,
        component_config: ComponentConfig,
        global_configs: ComponentGlobalConfigs,
        ipc_in: BinaryIO,
        ipc_out: BinaryIO,
    ):
        super().__init__(component_id, component_config, global_configs)

        self._ipc_in: BinaryIO = ipc_in
        self._ipc_out: BinaryIO = ipc_out

    async def _send_message(self, message: bytes) -> None:
        await self._loop.run_in_executor(None, self._write_frame, message)

    async def _recv_message(self) -> Optional[bytes]:
        return await self._loop.run_in_executor(None, self._read_frame)

    def _close_transport(self) -> None:
        for resource in (self._ipc_in, self._ipc_out):
            try:
                resource.close()
            except Exception:
                pass

    def _write_frame(self, message: bytes) -> None:
        self._ipc_out.write(message)
        self._ipc_out.flush()

    def _read_frame(self) -> Optional[bytes]:
        prefix = self._read_exactly(_IPC_FRAME_PREFIX_SIZE)

        if prefix is None:
            return None

        header_length, binary_length = _IPC_FRAME_PREFIX.unpack(prefix)
        body = self._read_exactly(header_length + binary_length)

        if body is None:
            return None

        return prefix + body

    def _read_exactly(self, length: int) -> Optional[bytes]:
        buffer = bytearray()

        while len(buffer) < length:
            chunk = self._ipc_in.read(length - len(buffer))

            if not chunk:
                return None

            buffer.extend(chunk)

        return bytes(buffer)

class ComponentRemoteVirtualEnvRuntimeProxy(ComponentRuntimeProxy):
    """SSH-exec-based IPC proxy for remote venv workers."""
    channel: SshExecChannel

    async def _send_message(self, message: bytes) -> None:
        await self.channel.send(message)

    async def _recv_message(self) -> Optional[bytes]:
        return await self.channel.recv()

def main() -> None:
    """Remote entrypoint when launched as
    ``python -m mindor.core.component.runtime.virtualenv.remote`` on the SSH target.

    The remote venv's python has carved off stdin/stdout as the IPC pair
    (via ``IpcStdioChannel.setup()``) and redirects fd 0/1 to stderr so
    user-code ``print(...)`` cannot corrupt the IPC stream.
    """
    channel = IpcStdioChannel(stdio_worker_factory(ComponentRemoteVirtualEnvRuntimeWorker))
    channel.setup()
    channel.run()

if __name__ == "__main__":
    main()
