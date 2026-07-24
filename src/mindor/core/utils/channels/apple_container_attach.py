from __future__ import annotations

from typing import Optional
import asyncio, struct

# IPC frame prefix shared with IpcMessage: header_len + binary_len (BE u32).
_IPC_FRAME_PREFIX = struct.Struct(">II")
_IPC_FRAME_PREFIX_SIZE = _IPC_FRAME_PREFIX.size

class AppleContainerAttachChannel:
    """Bidirectional length-prefixed bytes channel over a `container start -a -i`
    subprocess. The subprocess's stdin/stdout become the channel's write/read
    ends. stderr is drained separately into the manager's log so it does not
    corrupt the IPC stream.

    Framing: callers pass complete `IpcMessage.serialize()` frames whose first
    8 bytes encode header_len + binary_len; `send` writes them as-is and `recv`
    reads the prefix then reads exactly the body length.
    """
    def __init__(self, process: asyncio.subprocess.Process):
        if process.stdin is None or process.stdout is None:
            raise RuntimeError("AppleContainerAttachChannel requires stdin and stdout pipes")

        self._process: asyncio.subprocess.Process = process
        self._stdin: asyncio.StreamWriter = process.stdin
        self._stdout: asyncio.StreamReader = process.stdout
        self._closed = False

    async def send(self, message: bytes) -> None:
        if self._closed:
            raise RuntimeError("AppleContainerAttachChannel is closed")

        self._stdin.write(message)
        await self._stdin.drain()

    async def recv(self) -> Optional[bytes]:
        if self._closed:
            return None

        try:
            prefix = await self._stdout.readexactly(_IPC_FRAME_PREFIX_SIZE)
        except asyncio.IncompleteReadError:
            return None

        header_length, binary_length = _IPC_FRAME_PREFIX.unpack(prefix)

        try:
            body = await self._stdout.readexactly(header_length + binary_length)
        except asyncio.IncompleteReadError:
            return None

        return prefix + body

    def close(self) -> None:
        if self._closed:
            return

        self._closed = True

        try:
            self._stdin.close()
        except Exception:
            pass

        if self._process.returncode is None:
            try:
                self._process.terminate()
            except Exception:
                pass
