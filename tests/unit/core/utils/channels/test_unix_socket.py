"""Tests for UnixSocketChannel / UnixSocketListener (line-framed bytes transport).

The channel adds `\\n` on send and strips it on recv; callers always work with
unframed messages. The listener owns the socket path and unlinks it on close.
"""

from __future__ import annotations

import os
import socket
import stat
import tempfile
import threading
from typing import Tuple

import pytest

from mindor.core.utils.channels.unix_socket import (
    UnixSocketChannel,
    UnixSocketListener,
)


def _socket_path() -> str:
    fd, path = tempfile.mkstemp(prefix="msc-", suffix=".sock")
    os.close(fd)
    os.unlink(path)  # mkstemp creates a regular file; bind needs a free path
    return path


def _make_pair() -> Tuple[UnixSocketListener, UnixSocketChannel, UnixSocketChannel]:
    path = _socket_path()
    listener = UnixSocketListener(path)

    accepted: list = []

    def _accept():
        accepted.append(listener.accept())

    thread = threading.Thread(target=_accept)
    thread.start()
    try:
        client = UnixSocketChannel.connect(path)
        thread.join(timeout=5.0)
    except Exception:
        listener.close()
        raise
    if thread.is_alive() or not accepted:
        listener.close()
        client.close()
        raise RuntimeError("accept did not complete in time")
    server = accepted[0]
    return listener, server, client


class TestUnixSocketChannel:
    def test_send_recv_single_message(self):
        listener, server, client = _make_pair()
        try:
            client.send(b"hello")
            assert server.recv() == b"hello"
        finally:
            client.close()
            server.close()
            listener.close()

    def test_bidirectional_send_recv(self):
        listener, server, client = _make_pair()
        try:
            client.send(b"ping")
            assert server.recv() == b"ping"

            server.send(b"pong")
            assert client.recv() == b"pong"
        finally:
            client.close()
            server.close()
            listener.close()

    def test_multiple_messages_in_order(self):
        listener, server, client = _make_pair()
        try:
            client.send(b"first")
            client.send(b"second")
            client.send(b"third")
            assert server.recv() == b"first"
            assert server.recv() == b"second"
            assert server.recv() == b"third"
        finally:
            client.close()
            server.close()
            listener.close()

    def test_channel_strips_newline_framing(self):
        listener, server, client = _make_pair()
        try:
            client.send(b"payload")
            received = server.recv()
            assert received == b"payload"
            assert not received.endswith(b"\n")
        finally:
            client.close()
            server.close()
            listener.close()

    def test_recv_returns_none_when_peer_closes(self):
        listener, server, client = _make_pair()
        try:
            client.close()
            assert server.recv() is None
        finally:
            server.close()
            listener.close()

    def test_recv_returns_none_after_close(self):
        listener, server, client = _make_pair()
        try:
            client.close()
            assert client.recv() is None
        finally:
            server.close()
            listener.close()

    def test_send_after_close_raises(self):
        listener, server, client = _make_pair()
        try:
            client.close()
            with pytest.raises(RuntimeError, match="closed"):
                client.send(b"x")
        finally:
            server.close()
            listener.close()

    def test_close_is_idempotent(self):
        listener, server, client = _make_pair()
        try:
            client.close()
            client.close()  # second close must not raise
        finally:
            server.close()
            listener.close()


class TestUnixSocketListener:
    def test_bind_creates_socket_file_with_mode(self):
        path = _socket_path()
        listener = UnixSocketListener(path, mode=0o600)
        try:
            assert os.path.exists(path)
            assert stat.S_ISSOCK(os.stat(path).st_mode)
            # Permission bits should match mode (mask off type bits).
            assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
        finally:
            listener.close()

    def test_close_unlinks_socket_file(self):
        path = _socket_path()
        listener = UnixSocketListener(path)
        assert os.path.exists(path)
        listener.close()
        assert not os.path.exists(path)

    def test_close_is_idempotent(self):
        path = _socket_path()
        listener = UnixSocketListener(path)
        listener.close()
        listener.close()  # second close must not raise

    def test_replaces_stale_socket_file(self):
        path = _socket_path()
        # Pre-create a stale socket file to simulate a previous run.
        with open(path, "wb") as f:
            f.write(b"stale")
        listener = UnixSocketListener(path)
        try:
            assert stat.S_ISSOCK(os.stat(path).st_mode)
        finally:
            listener.close()

    def test_accept_after_close_raises(self):
        path = _socket_path()
        listener = UnixSocketListener(path)
        listener.close()
        with pytest.raises(RuntimeError, match="closed"):
            listener.accept()

    def test_accept_timeout_raises(self):
        path = _socket_path()
        listener = UnixSocketListener(path)
        try:
            with pytest.raises(socket.timeout):
                listener.accept(timeout=0.05)
        finally:
            listener.close()

    def test_context_manager_closes(self):
        path = _socket_path()
        with UnixSocketListener(path) as listener:
            assert os.path.exists(path)
        assert not os.path.exists(path)
