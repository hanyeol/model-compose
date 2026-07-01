"""Tests for SubprocessPipeChannel (line-framed bytes transport).

The channel adds `\\n` on send and strips it on recv; callers always work with
unframed messages.
"""

from __future__ import annotations

import os

import pytest

from mindor.core.utils.channels.subprocess_pipe import SubprocessPipeChannel


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
            parent.send(b"hello")
            assert child.recv() == b"hello"
        finally:
            parent.close()
            child.close()

    def test_bidirectional_send_recv(self):
        parent, child = _make_pair()
        try:
            parent.send(b"ping")
            assert child.recv() == b"ping"

            child.send(b"pong")
            assert parent.recv() == b"pong"
        finally:
            parent.close()
            child.close()

    def test_multiple_messages_in_order(self):
        parent, child = _make_pair()
        try:
            parent.send(b"first")
            parent.send(b"second")
            parent.send(b"third")
            assert child.recv() == b"first"
            assert child.recv() == b"second"
            assert child.recv() == b"third"
        finally:
            parent.close()
            child.close()

    def test_channel_adds_newline_framing(self):
        # Verify framing semantics: peer receives the message without trailing \n.
        parent, child = _make_pair()
        try:
            parent.send(b"payload")
            received = child.recv()
            assert received == b"payload"
            assert not received.endswith(b"\n")
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
                ch.send(b"hi")  # opens fine
            # After exit, send must raise.
            with pytest.raises(RuntimeError, match="closed"):
                ch.send(b"x")
        finally:
            for fd in (a_r, b_w):
                try:
                    os.close(fd)
                except OSError:
                    pass
