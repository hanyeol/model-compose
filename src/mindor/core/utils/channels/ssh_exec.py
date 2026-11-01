from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional
import asyncio, struct

if TYPE_CHECKING:
    import paramiko

# IPC frame prefix shared with IpcMessage: header_len + binary_len (BE u32).
_IPC_FRAME_PREFIX = struct.Struct(">II")
_IPC_FRAME_PREFIX_SIZE = _IPC_FRAME_PREFIX.size

class SshExecChannel:
    """Bidirectional length-prefixed bytes channel over an SSH exec channel.

    Mirrors `AppleContainerAttachChannel`'s shape: the channel wraps a backend
    primitive (here, a paramiko ``Channel`` returned by ``exec_command``) and
    exposes async ``send(bytes) -> None`` / ``recv() -> Optional[bytes]`` /
    ``close()``.

    Wire:
    - **Send (host → remote)**: written to the exec channel's stdin stream.
      Callers pass complete ``IpcMessage.serialize()`` frames (8B prefix + body);
      the remote worker parses them by reading the prefix first.
    - **Recv (remote → host)**: read from the exec channel's stdout stream. The
      remote worker is expected to carve off stdin/stdout as the IPC pair (see
      ``IpcStdioChannel``), so stderr carries log output and does not corrupt
      the IPC stream.

    paramiko ``Channel`` is blocking; every I/O call is dispatched to a thread
    so the caller stays on the event loop. ``SshClient`` already follows the
    same pattern for its own methods.
    """
    def __init__(self, channel: paramiko.Channel):
        self._channel: paramiko.Channel = channel
        self._closed = False

    async def send(self, message: bytes) -> None:
        if self._closed:
            raise RuntimeError("SshExecChannel is closed")

        await asyncio.to_thread(self._channel.sendall, message)

    async def recv(self) -> Optional[bytes]:
        if self._closed:
            return None

        prefix = await self._read_exactly(_IPC_FRAME_PREFIX_SIZE)

        if prefix is None:
            return None

        header_length, binary_length = _IPC_FRAME_PREFIX.unpack(prefix)
        body = await self._read_exactly(header_length + binary_length)

        if body is None:
            return None

        return prefix + body

    def close(self) -> None:
        if self._closed:
            return

        self._closed = True

        try:
            self._channel.shutdown_write()
        except Exception:
            pass

        try:
            self._channel.close()
        except Exception:
            pass

    async def _read_exactly(self, length: int) -> Optional[bytes]:
        buffer = bytearray()

        while len(buffer) < length:
            chunk = await asyncio.to_thread(self._channel.recv, length - len(buffer))

            if not chunk:
                return None

            buffer.extend(chunk)

        return bytes(buffer)
