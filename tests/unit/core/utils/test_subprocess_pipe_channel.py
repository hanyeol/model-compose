"""Tests for SubprocessPipeChannel (JSON-lines + payload codec)."""

from __future__ import annotations

import os
import io
import socket
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import BaseModel

from mindor.core.utils.subprocess import (
    SubprocessPipeChannel,
    dumps,
    loads,
)


class SamplePydantic(BaseModel):
    name: str
    value: int


class TestCodec:
    def test_primitive_roundtrip(self):
        msg = {"type": "run", "payload": {"x": 1, "y": "abc", "z": [1, 2, 3]}}
        assert loads(dumps(msg)) == msg

    def test_bytes_envelope(self):
        msg = {"payload": {"data": b"\x00\x01\x02"}}
        encoded = dumps(msg)
        decoded = loads(encoded)
        assert decoded["payload"]["data"] == b"\x00\x01\x02"

    def test_datetime_to_iso(self):
        dt = datetime(2025, 1, 2, 3, 4, 5)
        out = loads(dumps({"ts": dt}))
        assert out["ts"] == dt.isoformat()

    def test_path_to_string(self):
        out = loads(dumps({"p": Path("/tmp/x")}))
        assert out["p"] == "/tmp/x" or out["p"].endswith("x")

    def test_pydantic_model_dumped(self):
        m = SamplePydantic(name="a", value=42)
        out = loads(dumps({"m": m}))
        assert out["m"] == {"name": "a", "value": 42}

    def test_rejects_file_like(self):
        with pytest.raises(TypeError, match="SubprocessPipeChannel"):
            dumps({"f": io.BytesIO(b"x")})

    def test_rejects_socket(self):
        s = socket.socket()
        try:
            with pytest.raises(TypeError, match="SubprocessPipeChannel"):
                dumps({"s": s})
        finally:
            s.close()


class TestSubprocessPipeChannel:
    def test_send_recv_roundtrip(self):
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

        try:
            parent.send({"type": "ping", "payload": {"n": 1}})
            received = child.recv()
            assert received == {"type": "ping", "payload": {"n": 1}}

            child.send({"type": "pong", "payload": {"n": 2}})
            received = parent.recv()
            assert received == {"type": "pong", "payload": {"n": 2}}
        finally:
            parent.close()
            child.close()

    def test_recv_raises_eoferror_when_peer_closes(self):
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

        try:
            child.close()  # peer goes away
            with pytest.raises(EOFError):
                parent.recv()
        finally:
            parent.close()

    def test_recv_raises_eoferror_after_close(self):
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

        with pytest.raises(EOFError):
            channel.recv()
