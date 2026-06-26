from __future__ import annotations

from typing import IO, Optional
import os


class SubprocessPipeChannel:
    """Bidirectional line-framed bytes channel over two OS pipe file descriptors.

    `request_fd` is read for incoming messages, `response_fd` is written to for outgoing
    messages. The constructor takes ownership of the fds and closes them on `.close()`.

    Framing: callers pass whole messages without a trailing newline; the channel
    appends `\\n` on send and strips it on recv. Encoding (e.g., JSON-lines via a
    codec) is the caller's responsibility.
    """

    def __init__(self, request_fd: int, response_fd: int):
        self._reader: IO[bytes] = os.fdopen(request_fd, "rb", buffering=0)
        self._writer: IO[bytes] = os.fdopen(response_fd, "wb", buffering=0)
        self._closed = False

    def send(self, message: bytes) -> None:
        if self._closed:
            raise RuntimeError("SubprocessPipeChannel is closed")
        self._writer.write(message + b"\n")

    def recv(self) -> Optional[bytes]:
        if self._closed:
            return None
        line = self._reader.readline()
        if not line:
            return None
        return line.rstrip(b"\n")

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._reader.close()
        except Exception:
            pass
        try:
            self._writer.close()
        except Exception:
            pass

    def __enter__(self) -> "SubprocessPipeChannel":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
