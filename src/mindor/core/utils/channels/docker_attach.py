from __future__ import annotations

from typing import Optional
import os, socket, struct

# Docker's attach stream multiplex header format (non-TTY mode):
#   8 bytes: { stream_type:u8, pad:u24, length:u32 (big endian) }
#   payload: `length` bytes
# stream_type: 1 = stdout, 2 = stderr (0 = stdin is never received this way).
_FRAME_HEADER = struct.Struct(">BxxxL")
_STDOUT = 1

class DockerAttachChannel:
    """Bidirectional line-framed bytes channel over a docker `attach` socket.

    Exposes a `send(bytes) -> None` / `recv() -> Optional[bytes]` / `close()`
    interface against the daemon's attach stream.

    Wire:
    - **Send (host → container)**: written directly to the attach socket.
      Docker forwards the bytes verbatim to the container's stdin. We append
      `\\n` per message; the container reads with `readline()`.
    - **Recv (container → host)**: docker frames stdout/stderr with an 8-byte
      multiplex header (non-TTY mode). We demultiplex and yield only stdout
      payload as bytes, dropping stderr frames (which carry user logs — the
      caller can subscribe via `docker logs` or a sidecar stream if needed).
      Stdout payload is buffered and re-framed by `\\n`.

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
        # Docker daemon forwards stdin bytes verbatim. We append `\n` so
        # the container can read messages with `readline()`.
        self._sock.sendall(message + b"\n")

    def recv(self) -> Optional[bytes]:
        if self._closed:
            return None
        while True:
            newline_idx = self._recv_buffer.find(b"\n")
            if newline_idx >= 0:
                line = bytes(self._recv_buffer[:newline_idx])
                del self._recv_buffer[: newline_idx + 1]
                return line

            # Need more bytes — pull the next stdout frame from the wire.
            payload = self._read_one_stdout_frame()
            if payload is None:
                # EOF. Drain any partial line we have so the caller still sees
                # the last message, then return None on the subsequent call.
                if self._recv_buffer:
                    line = bytes(self._recv_buffer)
                    self._recv_buffer.clear()
                    self._closed = True
                    return line
                self._closed = True
                return None
            self._recv_buffer.extend(payload)

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
