from typing import Optional, Dict, Any
from enum import Enum
from dataclasses import dataclass, field
from pydantic import BaseModel
from mindor.dsl.schema.component import ComponentConfig
from mindor.core.component.base import ComponentGlobalConfigs
import json, struct, time

# Wire frame prefix: header_len (BE u32) + binary_len (BE u32).
# Followed by `header_len` bytes of JSON header, then `binary_len` bytes of
# opaque binary payload. `binary_len == 0` means no binary trailer.
#
# The binary trailer travels out-of-band from the JSON header — used for
# STREAM_CHUNK BYTES payloads to avoid base64 overhead, but not tied to any
# particular message type. Channels only need to read the 8-byte prefix to
# know the total frame size; they do not interpret the JSON header.
_FRAME_PREFIX = struct.Struct(">II")
_FRAME_PREFIX_SIZE = _FRAME_PREFIX.size  # 8

class IpcMessageType(str, Enum):
    """IPC message types for process communication"""
    START        = "start"
    STOP         = "stop"
    RUN          = "run"
    CANCEL       = "cancel"
    RESULT       = "result"
    ERROR        = "error"
    HEARTBEAT    = "heartbeat"
    STATUS       = "status"
    LOG          = "log"
    # Stream multiplexing
    STREAM_PULL  = "stream_pull"
    STREAM_CHUNK = "stream_chunk"
    STREAM_END   = "stream_end"
    STREAM_ABORT = "stream_abort"
    STREAM_CLOSE = "stream_close"

@dataclass
class IpcMessage:
    """Message format for inter-process communication.

    `binary` is an optional opaque bytes trailer transmitted alongside the
    JSON header but not embedded in it. Any message type may carry a binary
    trailer; currently STREAM_CHUNK uses it for BYTES-kind stream payloads.
    """
    type: IpcMessageType
    request_id: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))
    binary: Optional[bytes] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the JSON header to a dictionary. Excludes the binary trailer."""
        return {
            "type": self.type.value,
            "request_id": self.request_id,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }

    def serialize(self) -> bytes:
        """Serialize to a complete wire frame: 8-byte prefix + JSON header + binary trailer."""
        header = json.dumps(self.to_dict(), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        binary = self.binary or b""
        return _FRAME_PREFIX.pack(len(header), len(binary)) + header + binary

    @classmethod
    def deserialize(cls, data: bytes) -> "IpcMessage":
        """Reconstruct an IpcMessage from a complete wire frame."""
        if len(data) < _FRAME_PREFIX_SIZE:
            raise ValueError(f"IPC frame too short: {len(data)} bytes")

        header_length, binary_length = _FRAME_PREFIX.unpack_from(data, 0)
        expected_length = _FRAME_PREFIX_SIZE + header_length + binary_length

        if len(data) != expected_length:
            raise ValueError(f"IPC frame length mismatch: expected {expected_length} bytes, got {len(data)}")

        header_end = _FRAME_PREFIX_SIZE + header_length
        header_dict = json.loads(data[_FRAME_PREFIX_SIZE:header_end].decode("utf-8"))
        binary = bytes(data[header_end:header_end + binary_length]) if binary_length else None

        return cls(
            type=header_dict["type"],
            request_id=header_dict.get("request_id"),
            payload=header_dict.get("payload"),
            timestamp=header_dict.get("timestamp", int(time.time() * 1000)),
            binary=binary,
        )

class IpcStartPayload(BaseModel):
    """START message payload carrying the embedded component's config bundle."""
    component_id: str
    component_config: ComponentConfig
    global_configs: ComponentGlobalConfigs
