from __future__ import annotations

from typing import Optional
import os, socket, struct

# Docker's attach stream multiplex header format (non-TTY mode):
#   8 bytes: { stream_type:u8, pad:u24, length:u32 (big endian) }
#   payload: `length` bytes
# stream_type: 1 = stdout, 2 = stderr (0 = stdin is never received this way).
_FRAME_HEADER = struct.Struct(">BxxxL")
_STDOUT = 1

# IPC frame prefix shared with IpcMessage: header_len + binary_len (BE u32).
_IPC_FRAME_PREFIX = struct.Struct(">II")
_IPC_FRAME_PREFIX_SIZE = _IPC_FRAME_PREFIX.size

class DockerAttachChannel:
    """Bidirectional length-prefixed bytes channel over a docker `attach` socket.

    Exposes a `send(bytes) -> None` / `recv() -> Optional[bytes]` / `close()`
    interface against the daemon's attach stream.

    Wire:
    - **Send (host → container)**: written directly to the attach socket.
      Docker forwards the bytes verbatim to the container's stdin. Callers pass
      complete `IpcMessage.serialize()` frames (8B prefix + body); the container
      parses them by reading the prefix first.
    - **Recv (container → host)**: docker frames stdout/stderr with an 8-byte
      multiplex header (non-TTY mode). We demultiplex and yield only stdout
      payload as bytes, dropping stderr frames (which carry user logs — the
      caller can subscribe via `docker logs` or a sidecar stream if needed).
      Stdout payload is buffered and re-framed by the IPC length prefix.

    The container is expected to be started with `tty=False, stdin_open=True`
    so the daemon emits framed output.
    """
    def __init__(self, sock):
        # `sock` may be the raw socket object returned by docker SDK's
        # `attach_socket`, or a SocketIO-like wrapper. We unwrap to the
        # underlying socket so blocking recv works predictably across SDK
        # versions.
        if hasattr(sock, "_sock"):
            sock = sock._sock

        self._sock: socket.socket = sock
        self._closed = False
        self._recv_buffer = bytearray()

    def send(self, message: bytes) -> None:
        if self._closed:
            raise RuntimeError("DockerAttachChannel is closed")

        # Docker daemon forwards stdin bytes verbatim. The message is already
        # a length-prefixed IPC frame; the container parses it by prefix.
        self._sock.sendall(message)

    def recv(self) -> Optional[bytes]:
        if self._closed:
            return None

        prefix = self._read_ipc_bytes(_IPC_FRAME_PREFIX_SIZE)

        if prefix is None:
            return None

        header_length, binary_length = _IPC_FRAME_PREFIX.unpack(prefix)
        body = self._read_ipc_bytes(header_length + binary_length)

        if body is None:
            return None

        return prefix + body

    def close(self) -> None:
        if self._closed:
            return

        self._closed = True

        try:
            self._sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

        try:
            self._sock.close()
        except OSError:
            pass

    def _read_ipc_bytes(self, n: int) -> Optional[bytes]:
        """Read exactly `n` bytes of demuxed stdout payload from the wire."""
        buffer = bytearray()

        while len(buffer) < n:
            if not self._recv_buffer:
                payload = self._read_one_stdout_frame()

                if payload is None:
                    self._closed = True
                    return None

                self._recv_buffer.extend(payload)

            take = min(n - len(buffer), len(self._recv_buffer))
            buffer.extend(self._recv_buffer[:take])
            del self._recv_buffer[:take]

        return bytes(buffer)

    def _read_one_stdout_frame(self) -> Optional[bytes]:
        """Read the next non-TTY mux frame and return its payload iff it is a
        stdout frame. Stderr frames are dropped (user code logs)."""
        while True:
            header = self._read_exactly(8)

            if header is None:
                return None

            stream_type, length = _FRAME_HEADER.unpack(header)

            if length == 0:
                continue

            payload = self._read_exactly(length)

            if payload is None:
                return None

            if stream_type == _STDOUT:
                return payload
            # stderr (or any other stream) → drop and keep reading.

    def _read_exactly(self, n: int) -> Optional[bytes]:
        buf = bytearray()

        while len(buf) < n:
            chunk = self._sock.recv(n - len(buf))

            if not chunk:
                return None

            buf.extend(chunk)

        return bytes(buf)
