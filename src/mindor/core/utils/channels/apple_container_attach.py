from __future__ import annotations

from typing import Optional
import asyncio

class AppleContainerAttachChannel:
    """Bidirectional line-framed bytes channel over a `container start -a -i`
    subprocess. The subprocess's stdin/stdout become the channel's write/read
    ends. stderr is drained separately into the manager's log so it does not
    corrupt the IPC stream.

    Framing: callers pass whole messages without a trailing newline; the
    channel appends `\\n` on send and strips it on recv.
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

        self._stdin.write(message + b"\n")
        await self._stdin.drain()

    async def recv(self) -> Optional[bytes]:
        if self._closed:
            return None
        line = await self._stdout.readline()
        if not line:
            return None
        return line.rstrip(b"\n")

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
