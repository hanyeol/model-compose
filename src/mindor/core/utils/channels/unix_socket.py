from __future__ import annotations

from typing import Optional
import os, socket

class UnixSocketChannel:
    """Bidirectional line-framed bytes channel over a connected Unix domain socket.

    Mirrors `SubprocessPipeChannel`'s `send(bytes) -> None` / `recv() -> Optional[bytes]`
    / `close()` interface. Encoding (e.g., `IpcMessage.serialize`) is the caller's
    responsibility.

    Framing: callers pass whole messages without a trailing newline; the channel
    appends `\\n` on send and strips it on recv.

    Connection-oriented; one channel wraps exactly one accepted/connected socket.
    """
    def __init__(self, sock: socket.socket):
        self._sock = sock
        self._reader = sock.makefile("rb", buffering=0)
        self._writer = sock.makefile("wb", buffering=0)
        self._closed = False

    @classmethod
    def connect(cls, path: str) -> "UnixSocketChannel":
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(path)

        return cls(sock)

    def send(self, message: bytes) -> None:
        if self._closed:
            raise RuntimeError("UnixSocketChannel is closed")

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

        for resource in (self._reader, self._writer, self._sock):
            try:
                resource.close()
            except Exception:
                pass

class UnixSocketListener:
    """Listening Unix domain socket helper.

    Owns the listening socket and its filesystem path. `accept()` returns one
    `UnixSocketChannel` per inbound connection. `close()` shuts down the listener
    and unlinks the socket file.
    """
    def __init__(self, path: str, mode: int = 0o600, backlog: int = 1):
        self.path = path
        self._sock: Optional[socket.socket] = None
        self._closed = False

        # Remove any stale socket file from a previous run before binding.
        try:
            if os.path.exists(path):
                os.unlink(path)
        except OSError:
            pass

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(path)
        os.chmod(path, mode)
        sock.listen(backlog)
        self._sock = sock

    def accept(self, timeout: Optional[float] = None) -> UnixSocketChannel:
        if self._sock is None:
            raise RuntimeError("UnixSocketListener is closed")
        self._sock.settimeout(timeout)
        try:
            conn, _ = self._sock.accept()
        finally:
            self._sock.settimeout(None)
        conn.settimeout(None)
        return UnixSocketChannel(conn)

    def close(self) -> None:
        if self._closed:
            return

        self._closed = True

        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
        try:
            if os.path.exists(self.path):
                os.unlink(self.path)
        except OSError:
            pass

    def __enter__(self) -> UnixSocketListener:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
