"""Unit tests for `DockerAttachChannel`.

The channel wraps a docker `attach` socket and:
- Writes bytes verbatim to the socket (stdin → container). Callers pass
  complete IPC frames (8B prefix + body).
- Demultiplexes 8-byte framed stdout/stderr (container → host) and reads
  IPC frames off the stdout stream. Stderr frames are dropped (they carry
  user-code logs that `docker logs` will also capture).

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

_FRAME_HEADER = struct.Struct(">BxxxL")
_STDOUT = 1
_STDERR = 2

_IPC_PREFIX = struct.Struct(">II")


def _mux(stream: int, payload: bytes) -> bytes:
    """Docker attach non-TTY mux frame around a stdout/stderr payload."""
    return _FRAME_HEADER.pack(stream, len(payload)) + payload


def _ipc(header: bytes, binary: bytes = b"") -> bytes:
    """Build a complete IPC frame: 8B prefix + header + binary."""
    return _IPC_PREFIX.pack(len(header), len(binary)) + header + binary


def _pair():
    """Return (channel_sock, peer_sock). The channel side is wrapped in
    `DockerAttachChannel`; the peer side acts as the docker daemon."""
    a, b = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    return a, b


class TestSend:
    def test_send_writes_bytes_verbatim(self):
        a, b = _pair()
        try:
            channel = DockerAttachChannel(a)
            frame = _ipc(b'{"type":"run"}')
            channel.send(frame)
            assert b.recv(1024) == frame
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
    def test_recv_single_ipc_frame_in_one_stdout_frame(self):
        a, b = _pair()
        try:
            channel = DockerAttachChannel(a)
            frame = _ipc(b"hello")
            b.sendall(_mux(_STDOUT, frame))
            assert channel.recv() == frame
        finally:
            a.close(); b.close()

    def test_recv_drops_stderr_frames(self):
        """Stderr is user-code log noise; the channel must transparently
        skip stderr frames and surface only stdout payload."""
        a, b = _pair()
        try:
            channel = DockerAttachChannel(a)
            frame = _ipc(b"ipc-message")
            b.sendall(_mux(_STDERR, b"loaded model\n"))
            b.sendall(_mux(_STDERR, b"warming up\n"))
            b.sendall(_mux(_STDOUT, frame))
            assert channel.recv() == frame
        finally:
            a.close(); b.close()

    def test_recv_handles_ipc_frame_split_across_stdout_frames(self):
        """One IPC frame can arrive in multiple stdout mux frames — the
        daemon's framing has no relation to IPC framing."""
        a, b = _pair()
        try:
            channel = DockerAttachChannel(a)
            frame = _ipc(b"hello world")
            # Split the IPC frame into three arbitrary chunks across mux frames.
            b.sendall(_mux(_STDOUT, frame[:3]))
            b.sendall(_mux(_STDOUT, frame[3:9]))
            b.sendall(_mux(_STDOUT, frame[9:]))
            assert channel.recv() == frame
        finally:
            a.close(); b.close()

    def test_recv_handles_multiple_ipc_frames_in_one_stdout_frame(self):
        """Two IPC frames can be packed into a single stdout mux frame."""
        a, b = _pair()
        try:
            channel = DockerAttachChannel(a)
            f1 = _ipc(b"first")
            f2 = _ipc(b"second")
            b.sendall(_mux(_STDOUT, f1 + f2))
            assert channel.recv() == f1
            assert channel.recv() == f2
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

    def test_recv_returns_none_on_eof_mid_frame(self):
        """If the peer drops the connection mid-frame we surface EOF."""
        a, b = _pair()
        try:
            channel = DockerAttachChannel(a)
            frame = _ipc(b"complete")
            # Send only a partial IPC frame, then EOF.
            b.sendall(_mux(_STDOUT, frame[:5]))
            b.shutdown(socket.SHUT_WR); b.close()
            assert channel.recv() is None
        finally:
            a.close()

    def test_recv_drops_zero_length_mux_frames(self):
        """Daemons occasionally emit empty frames as keepalives; ignore them."""
        a, b = _pair()
        try:
            channel = DockerAttachChannel(a)
            frame = _ipc(b"payload")
            b.sendall(_mux(_STDOUT, b""))
            b.sendall(_mux(_STDOUT, frame))
            assert channel.recv() == frame
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
            frame = _ipc(b"hi")
            channel.send(frame)
            assert b.recv(1024) == frame
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

            ping = _ipc(b"ping")
            pong = _ipc(b"pong")
            ping2 = _ipc(b"ping2")
            pong2 = _ipc(b"pong2")

            channel.send(ping)
            b.sendall(_mux(_STDOUT, pong))
            channel.send(ping2)
            b.sendall(_mux(_STDOUT, pong2))
            b.shutdown(socket.SHUT_WR); b.close()

            t.join(timeout=2.0)
            assert results == [pong, pong2, None]
        finally:
            a.close()
