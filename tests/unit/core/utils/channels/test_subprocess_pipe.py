"""Tests for SubprocessPipeChannel (length-prefixed IPC frame transport).

Callers pass complete IPC frames whose first 8 bytes encode
`(header_len, binary_len)` in big-endian u32. The channel writes the blob
verbatim on `send` and reads back exactly one frame per `recv`.
"""

from __future__ import annotations

import os
import struct

import pytest

from mindor.core.utils.channels.subprocess_pipe import SubprocessPipeChannel

_FRAME_PREFIX = struct.Struct(">II")


def _ipc(header: bytes, binary: bytes = b"") -> bytes:
    return _FRAME_PREFIX.pack(len(header), len(binary)) + header + binary


def _make_pair():
    a_r, a_w = os.pipe()
    b_r, b_w = os.pipe()
    try:
        parent = SubprocessPipeChannel(request_fd=b_r, response_fd=a_w)
        child  = SubprocessPipeChannel(request_fd=a_r, response_fd=b_w)
    except Exception:
        for fd in (a_r, a_w, b_r, b_w):
            try:
                os.close(fd)
            except OSError:
                pass
        raise
    return parent, child


class TestSubprocessPipeChannel:
    def test_send_recv_single_message(self):
        parent, child = _make_pair()
        try:
            frame = _ipc(b"hello")
            parent.send(frame)
            assert child.recv() == frame
        finally:
            parent.close()
            child.close()

    def test_bidirectional_send_recv(self):
        parent, child = _make_pair()
        try:
            ping = _ipc(b"ping")
            pong = _ipc(b"pong")
            parent.send(ping)
            assert child.recv() == ping

            child.send(pong)
            assert parent.recv() == pong
        finally:
            parent.close()
            child.close()

    def test_multiple_messages_in_order(self):
        parent, child = _make_pair()
        try:
            f1 = _ipc(b"first")
            f2 = _ipc(b"second")
            f3 = _ipc(b"third")
            parent.send(f1)
            parent.send(f2)
            parent.send(f3)
            assert child.recv() == f1
            assert child.recv() == f2
            assert child.recv() == f3
        finally:
            parent.close()
            child.close()

    def test_frame_with_binary_trailer(self):
        parent, child = _make_pair()
        try:
            frame = _ipc(b'{"type":"chunk"}', b"\x00\x01\x02\x03")
            parent.send(frame)
            assert child.recv() == frame
        finally:
            parent.close()
            child.close()

    def test_recv_returns_none_when_peer_closes(self):
        parent, child = _make_pair()
        try:
            child.close()  # peer goes away
            assert parent.recv() is None
        finally:
            parent.close()

    def test_recv_returns_none_after_close(self):
        a_r, a_w = os.pipe()
        b_r, b_w = os.pipe()
        try:
            channel = SubprocessPipeChannel(request_fd=b_r, response_fd=a_w)
        except Exception:
            for fd in (a_r, a_w, b_r, b_w):
                try:
                    os.close(fd)
                except OSError:
                    pass
            raise

        channel.close()
        # Other side fds are no longer needed.
        for fd in (a_r, b_w):
            try:
                os.close(fd)
            except OSError:
                pass

        assert channel.recv() is None

    def test_send_after_close_raises(self):
        a_r, a_w = os.pipe()
        b_r, b_w = os.pipe()
        try:
            channel = SubprocessPipeChannel(request_fd=b_r, response_fd=a_w)
        except Exception:
            for fd in (a_r, a_w, b_r, b_w):
                try:
                    os.close(fd)
                except OSError:
                    pass
            raise

        channel.close()
        for fd in (a_r, b_w):
            try:
                os.close(fd)
            except OSError:
                pass

        with pytest.raises(RuntimeError, match="closed"):
            channel.send(b"x")

    def test_close_is_idempotent(self):
        parent, child = _make_pair()
        try:
            parent.close()
            parent.close()  # second close must not raise
        finally:
            child.close()

    def test_context_manager_closes(self):
        a_r, a_w = os.pipe()
        b_r, b_w = os.pipe()
        try:
            with SubprocessPipeChannel(request_fd=b_r, response_fd=a_w) as ch:
                ch.send(_ipc(b"hi"))  # opens fine
            # After exit, send must raise.
            with pytest.raises(RuntimeError, match="closed"):
                ch.send(b"x")
        finally:
            for fd in (a_r, b_w):
                try:
                    os.close(fd)
                except OSError:
                    pass
