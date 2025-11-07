from typing import Optional, Dict, Any
from enum import Enum
from dataclasses import dataclass, field
import time

class IpcMessageType(str, Enum):
    """IPC message types for process communication"""
    START     = "start"
    STOP      = "stop"
    RUN       = "run"
    RESULT    = "result"
    ERROR     = "error"
    HEARTBEAT = "heartbeat"
    STATUS    = "status"
    LOG       = "log"

@dataclass
class IpcMessage:
    """Message format for inter-process communication"""
    type: IpcMessageType
    request_id: str
    payload: Optional[Dict[str, Any]] = None
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))

    def to_params(self) -> Dict[str, Any]:
        """Serialize message to dictionary for IPC transmission"""
        return {
            "type": self.type.value,
            "request_id": self.request_id,
            "payload": self.payload,
            "timestamp": self.timestamp
        }
