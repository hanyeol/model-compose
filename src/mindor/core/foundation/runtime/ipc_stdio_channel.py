from __future__ import annotations

from typing import Any, BinaryIO, Callable, Optional
from mindor.core.foundation.runtime.ipc_message import IpcMessage, IpcMessageType
import asyncio, os, struct, sys

# IPC frame prefix shared with IpcMessage: header_len + binary_len (BE u32).
_IPC_FRAME_PREFIX = struct.Struct(">II")
_IPC_FRAME_PREFIX_SIZE = _IPC_FRAME_PREFIX.size

# Factory that builds the worker after the START handshake on a stdio channel.
# Receives the START message and the IPC file objects carved off stdin/stdout;
# returns anything with an async `run()`.
IpcStdioWorkerFactory = Callable[[IpcMessage, BinaryIO, BinaryIO], Any]

class IpcStdioChannel:
    """Hijacks stdin/stdout as an IPC channel and runs a worker over it.

    Used by worker entrypoints (e.g. container workers) where the parent
    attaches to the child's stdio: fd 0/1 carry IPC framed messages and fd 2
    is the log channel. `setup()` carves off fd 0/1 as the IPC pair and
    redirects them to stderr so user-code `print(...)` does not corrupt the
    IPC stream. `run()` performs the START handshake and drives the worker
    built by `worker_factory`.
    """
    def __init__(self, worker_factory: IpcStdioWorkerFactory) -> None:
        self.worker_factory: IpcStdioWorkerFactory = worker_factory
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

    def run(self) -> None:
        """Perform START handshake, build the worker via `worker_factory`, and drive it."""
        if self.ipc_in is None or self.ipc_out is None:
            raise RuntimeError("IpcStdioChannel.setup() must be called before run()")

        message = self._recv_message()
        if message.type != IpcMessageType.START:
            raise RuntimeError(
                f"Expected first IPC message of type 'start', got: {message.type!r}"
            )

        worker = self.worker_factory(message, self.ipc_in, self.ipc_out)
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
