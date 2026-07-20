from __future__ import annotations

from typing import IO, Optional
import os, struct

# Wire framing shared with IpcMessage: 8-byte prefix (header_len + binary_len,
# both BE u32) followed by header + binary bytes. The channel treats each
# whole frame as an opaque blob — it only reads the prefix to know the total
# body length.
_FRAME_PREFIX = struct.Struct(">II")
_FRAME_PREFIX_SIZE = _FRAME_PREFIX.size

class SubprocessPipeChannel:
    """Bidirectional length-prefixed bytes channel over two OS pipe file descriptors.

    `request_fd` is read for incoming messages, `response_fd` is written to for outgoing
    messages. The constructor takes ownership of the fds and closes them on `.close()`.

    Framing: callers pass complete `IpcMessage.serialize()` frames whose first
    8 bytes encode header_len + binary_len. `send` writes the blob as-is; `recv`
    reads the 8-byte prefix, then reads exactly `header_len + binary_len` more
    bytes and returns the full frame.
    """
    def __init__(self, request_fd: int, response_fd: int):
        self._reader: IO[bytes] = os.fdopen(request_fd, "rb", buffering=0)
        self._writer: IO[bytes] = os.fdopen(response_fd, "wb", buffering=0)
        self._closed = False

    def send(self, message: bytes) -> None:
        if self._closed:
            raise RuntimeError("SubprocessPipeChannel is closed")
        self._writer.write(message)

    def recv(self) -> Optional[bytes]:
        if self._closed:
            return None
        prefix = self._read_exactly(_FRAME_PREFIX_SIZE)
        if prefix is None:
            return None
        header_length, binary_length = _FRAME_PREFIX.unpack(prefix)
        body = self._read_exactly(header_length + binary_length)
        if body is None:
            return None
        return prefix + body

    def _read_exactly(self, length: int) -> Optional[bytes]:
        buffer = bytearray()

        while len(buffer) < length:
            chunk = self._reader.read(length - len(buffer))

            if not chunk:
                return None

            buffer.extend(chunk)

        return bytes(buffer)

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
