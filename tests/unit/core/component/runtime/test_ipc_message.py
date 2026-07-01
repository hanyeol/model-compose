"""Unit tests for `component/runtime/base/ipc_message.py`."""

from __future__ import annotations

import json

import pytest

from mindor.core.component.runtime.base.ipc_message import IpcMessage, IpcMessageType


class TestIpcMessageType:
    def test_lifecycle_members(self):
        assert IpcMessageType.START.value == "start"
        assert IpcMessageType.STOP.value == "stop"
        assert IpcMessageType.RUN.value == "run"
        assert IpcMessageType.RESULT.value == "result"
        assert IpcMessageType.ERROR.value == "error"
        assert IpcMessageType.HEARTBEAT.value == "heartbeat"
        assert IpcMessageType.STATUS.value == "status"
        assert IpcMessageType.LOG.value == "log"

    def test_stream_members(self):
        assert IpcMessageType.STREAM_PULL.value == "stream_pull"
        assert IpcMessageType.STREAM_CHUNK.value == "stream_chunk"
        assert IpcMessageType.STREAM_END.value == "stream_end"
        assert IpcMessageType.STREAM_ABORT.value == "stream_abort"
        assert IpcMessageType.STREAM_CLOSE.value == "stream_close"

    def test_string_enum_roundtrip(self):
        # str-Enum: equality with raw value and from-value reconstruction.
        assert IpcMessageType.RUN == "run"
        assert IpcMessageType("run") is IpcMessageType.RUN
        assert IpcMessageType("stream_pull") is IpcMessageType.STREAM_PULL


class TestIpcMessage:
    def test_minimal_creation(self):
        message = IpcMessage(type=IpcMessageType.HEARTBEAT)
        assert message.type is IpcMessageType.HEARTBEAT
        assert message.request_id is None
        assert message.payload is None
        assert isinstance(message.timestamp, int)
        assert message.timestamp > 0

    def test_creation_with_payload(self):
        message = IpcMessage(
            type=IpcMessageType.RUN,
            request_id="abc-123",
            payload={"input": {"x": 1}},
        )
        assert message.type is IpcMessageType.RUN
        assert message.request_id == "abc-123"
        assert message.payload == {"input": {"x": 1}}

    def test_to_dict_uses_enum_value(self):
        message = IpcMessage(type=IpcMessageType.RESULT, request_id="r1", payload={"output": 42})
        as_dict = message.to_dict()
        assert as_dict["type"] == "result"
        assert as_dict["request_id"] == "r1"
        assert as_dict["payload"] == {"output": 42}
        assert as_dict["timestamp"] == message.timestamp

    def test_serialize_is_json_bytes(self):
        message = IpcMessage(type=IpcMessageType.STATUS, payload={"status": "ready"})
        raw = message.serialize()
        assert isinstance(raw, bytes)
        decoded = json.loads(raw.decode("utf-8"))
        assert decoded["type"] == "status"
        assert decoded["payload"] == {"status": "ready"}

    def test_serialize_no_trailing_newline(self):
        message = IpcMessage(type=IpcMessageType.STOP)
        raw = message.serialize()
        # Channels (e.g., SubprocessPipeChannel) add the framing newline;
        # IpcMessage.serialize() must not include one.
        assert not raw.endswith(b"\n")

    def test_deserialize_roundtrip(self):
        original = IpcMessage(
            type=IpcMessageType.RUN,
            request_id="r-7",
            payload={"input": {"name": "ünîcødé"}},
        )
        restored = IpcMessage.deserialize(original.serialize())

        assert restored.type == IpcMessageType.RUN.value or restored.type is IpcMessageType.RUN
        assert restored.request_id == "r-7"
        assert restored.payload == {"input": {"name": "ünîcødé"}}
        assert restored.timestamp == original.timestamp

    def test_deserialize_stream_types(self):
        message = IpcMessage(
            type=IpcMessageType.STREAM_CHUNK,
            payload={"stream_id": "s1", "seq": 0, "data": "AAAA"},
        )
        restored = IpcMessage.deserialize(message.serialize())
        assert restored.type == IpcMessageType.STREAM_CHUNK.value
        assert restored.payload == {"stream_id": "s1", "seq": 0, "data": "AAAA"}
