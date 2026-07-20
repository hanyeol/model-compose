from __future__ import annotations

from typing import BinaryIO, Optional, Type
from mindor.core.component.runtime.common import ComponentRuntimeWorker
from mindor.core.component.runtime.base.ipc_message import IpcMessage, IpcMessageType, IpcStartPayload
import asyncio, os, struct, sys

# IPC frame prefix shared with IpcMessage: header_len + binary_len (BE u32).
_IPC_FRAME_PREFIX = struct.Struct(">II")
_IPC_FRAME_PREFIX_SIZE = _IPC_FRAME_PREFIX.size

class IpcStdioChannel:
    """Hijacks stdin/stdout as an IPC channel and runs a worker over it.

    Used by container worker entrypoints (Docker / Apple Container) where the
    parent attaches to the container's stdio: fd 0/1 carry IPC framed messages
    and fd 2 is the log channel. `setup()` carves off fd 0/1 as the IPC pair
    and redirects them to stderr so user-code `print(...)` does not corrupt
    the IPC stream. `run()` performs the INIT handshake and drives the worker.
    """
    def __init__(self) -> None:
        self.ipc_in: Optional[BinaryIO] = None
        self.ipc_out: Optional[BinaryIO] = None

    def setup(self) -> None:
        """Carve off stdin/stdout for IPC, then redirect fd 0/1 to stderr."""
        ipc_in_fd = os.dup(0)
        ipc_out_fd = os.dup(1)

        os.dup2(2, 0)
        os.dup2(2, 1)

        try:
            sys.stdin = os.fdopen(0, "r")
            sys.stdout = os.fdopen(1, "w", buffering=1)
        except Exception:
            # If reopening fails the redirected fds still work for raw writes;
            # only the buffered `print` path is degraded.
            pass

        self.ipc_in  = os.fdopen(ipc_in_fd, "rb", buffering=0)
        self.ipc_out = os.fdopen(ipc_out_fd, "wb", buffering=0)

    def run(self, worker_class: Type[ComponentRuntimeWorker]) -> None:
        """Perform INIT handshake, instantiate the worker, and run its event loop."""
        if self.ipc_in is None or self.ipc_out is None:
            raise RuntimeError("IpcStdioChannel.setup() must be called before run()")

        message = self._recv_message()
        if message.type != IpcMessageType.START:
            raise RuntimeError(
                f"Expected first IPC message of type 'start', got: {message.type!r}"
            )

        payload = IpcStartPayload.model_validate(message.payload or {})

        worker = worker_class(
            payload.component_id,
            payload.component_config,
            payload.global_configs,
            self.ipc_in,
            self.ipc_out,
        )

        asyncio.run(worker.run())

    def _recv_message(self) -> IpcMessage:
        """Read one length-prefixed IPC frame from the channel."""
        prefix = self._read_exactly(_IPC_FRAME_PREFIX_SIZE)

        if prefix is None:
            raise RuntimeError("Expected IPC message, got EOF")

        header_length, binary_length = _IPC_FRAME_PREFIX.unpack(prefix)
        body = self._read_exactly(header_length + binary_length)

        if body is None:
            raise RuntimeError("Expected IPC message body, got EOF")

        return IpcMessage.deserialize(prefix + body)

    def _read_exactly(self, length: int) -> Optional[bytes]:
        buffer = bytearray()

        while len(buffer) < length:
            chunk = self.ipc_in.read(length - len(buffer))

            if not chunk:
                return None

            buffer.extend(chunk)

        return bytes(buffer)
