from typing import Optional, Dict, Any
from enum import Enum
from dataclasses import dataclass, field
import json, time

class IpcMessageType(str, Enum):
    """IPC message types for process communication"""
    START        = "start"
    STOP         = "stop"
    RUN          = "run"
    RESULT       = "result"
    ERROR        = "error"
    HEARTBEAT    = "heartbeat"
    STATUS       = "status"
    LOG          = "log"
    # Stream multiplexing (see docs/specs/component-ipc.md §3.2)
    STREAM_PULL  = "stream_pull"
    STREAM_CHUNK = "stream_chunk"
    STREAM_END   = "stream_end"
    STREAM_ABORT = "stream_abort"
    STREAM_CLOSE = "stream_close"

@dataclass
class IpcMessage:
    """Message format for inter-process communication"""
    type: IpcMessageType
    request_id: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize message to dictionary for IPC transmission"""
        return {
            "type": self.type.value,
            "request_id": self.request_id,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }

    def serialize(self) -> bytes:
        """Serialize message to JSON bytes for wire transmission."""
        return json.dumps(self.to_dict(), ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    @classmethod
    def deserialize(cls, data: bytes) -> "IpcMessage":
        """Reconstruct an IpcMessage from JSON bytes received from the wire."""
        return cls(**json.loads(data.decode("utf-8")))
