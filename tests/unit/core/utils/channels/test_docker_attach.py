"""Unit tests for `DockerAttachChannel`.

The channel wraps a docker `attach` socket and:
- Writes raw bytes + `\\n` to the socket (stdin → container).
- Demultiplexes 8-byte framed stdout/stderr (container → host) and yields
  only stdout payload as line-framed bytes; stderr frames are dropped
  (they carry user-code logs that `docker logs` will also capture).

We don't actually need a docker daemon — `socket.socketpair()` plays both
sides of the wire.
"""

from __future__ import annotations

import socket
import struct
import threading
from typing import List, Optional

import pytest

from mindor.core.utils.channels.docker_attach import DockerAttachChannel

_HEADER = struct.Struct(">BxxxL")
_STDOUT = 1
_STDERR = 2


def _frame(stream: int, payload: bytes) -> bytes:
    return _HEADER.pack(stream, len(payload)) + payload


def _pair():
    """Return (channel_sock, peer_sock). The channel side is wrapped in
    `DockerAttachChannel`; the peer side acts as the docker daemon."""
    a, b = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    return a, b


class TestSend:
    def test_send_appends_newline(self):
        a, b = _pair()
        try:
            channel = DockerAttachChannel(a)
            channel.send(b"hello")
            assert b.recv(1024) == b"hello\n"
        finally:
            a.close(); b.close()

    def test_send_after_close_raises(self):
        a, b = _pair()
        try:
            channel = DockerAttachChannel(a)
            channel.close()
            with pytest.raises(RuntimeError, match="closed"):
                channel.send(b"x")
        finally:
            try: b.close()
            except OSError: pass


class TestRecv:
    def test_recv_single_stdout_frame_line(self):
        a, b = _pair()
        try:
            channel = DockerAttachChannel(a)
            b.sendall(_frame(_STDOUT, b"hello\n"))
            assert channel.recv() == b"hello"
        finally:
            a.close(); b.close()

    def test_recv_strips_trailing_newline_only(self):
        a, b = _pair()
        try:
            channel = DockerAttachChannel(a)
            b.sendall(_frame(_STDOUT, b"  spaced  \n"))
            assert channel.recv() == b"  spaced  "
        finally:
            a.close(); b.close()

    def test_recv_drops_stderr_frames(self):
        """Stderr is user-code log noise; the channel must transparently
        skip stderr frames and surface only stdout payload."""
        a, b = _pair()
        try:
            channel = DockerAttachChannel(a)
            b.sendall(_frame(_STDERR, b"loaded model\n"))
            b.sendall(_frame(_STDERR, b"warming up\n"))
            b.sendall(_frame(_STDOUT, b"ipc-message\n"))
            assert channel.recv() == b"ipc-message"
        finally:
            a.close(); b.close()

    def test_recv_handles_split_message_across_frames(self):
        """One IPC line can arrive in multiple stdout frames — the daemon's
        framing has no relation to the IPC line framing."""
        a, b = _pair()
        try:
            channel = DockerAttachChannel(a)
            b.sendall(_frame(_STDOUT, b"hel"))
            b.sendall(_frame(_STDOUT, b"lo "))
            b.sendall(_frame(_STDOUT, b"world\n"))
            assert channel.recv() == b"hello world"
        finally:
            a.close(); b.close()

    def test_recv_handles_multiple_lines_in_one_frame(self):
        """Two IPC messages can be packed into a single stdout frame."""
        a, b = _pair()
        try:
            channel = DockerAttachChannel(a)
            b.sendall(_frame(_STDOUT, b"first\nsecond\n"))
            assert channel.recv() == b"first"
            assert channel.recv() == b"second"
        finally:
            a.close(); b.close()

    def test_recv_returns_none_on_clean_eof(self):
        a, b = _pair()
        try:
            channel = DockerAttachChannel(a)
            b.shutdown(socket.SHUT_WR); b.close()
            assert channel.recv() is None
        finally:
            a.close()

    def test_recv_flushes_partial_line_on_eof(self):
        """If the peer drops the connection mid-line we still surface what
        we have, then EOF on the next call."""
        a, b = _pair()
        try:
            channel = DockerAttachChannel(a)
            b.sendall(_frame(_STDOUT, b"no-newline"))
            b.shutdown(socket.SHUT_WR); b.close()
            assert channel.recv() == b"no-newline"
            assert channel.recv() is None
        finally:
            a.close()

    def test_recv_drops_zero_length_frames(self):
        """Daemons occasionally emit empty frames as keepalives; ignore them."""
        a, b = _pair()
        try:
            channel = DockerAttachChannel(a)
            b.sendall(_frame(_STDOUT, b""))
            b.sendall(_frame(_STDOUT, b"payload\n"))
            assert channel.recv() == b"payload"
        finally:
            a.close(); b.close()


class TestUnwrap:
    """The docker SDK historically returned a SocketIO wrapper. We accept
    either it or a raw socket."""
    def test_unwraps_object_with_underscore_sock(self):
        a, b = _pair()
        try:
            class _Wrapper:
                def __init__(self, sock):
                    self._sock = sock
            channel = DockerAttachChannel(_Wrapper(a))
            channel.send(b"hi")
            assert b.recv(1024) == b"hi\n"
        finally:
            a.close(); b.close()


class TestThreaded:
    """Confirm the channel survives concurrent send/recv from different
    threads (the typical run_in_executor pattern)."""
    def test_concurrent_send_and_recv(self):
        a, b = _pair()
        results: List[Optional[bytes]] = []

        try:
            channel = DockerAttachChannel(a)

            def reader():
                while True:
                    msg = channel.recv()
                    results.append(msg)
                    if msg is None:
                        return

            t = threading.Thread(target=reader, daemon=True)
            t.start()

            channel.send(b"ping")
            b.sendall(_frame(_STDOUT, b"pong\n"))
            channel.send(b"ping2")
            b.sendall(_frame(_STDOUT, b"pong2\n"))
            b.shutdown(socket.SHUT_WR); b.close()

            t.join(timeout=2.0)
            assert results == [b"pong", b"pong2", None]
        finally:
            a.close()
