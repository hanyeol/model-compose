from typing import Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field
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

class IpcMessage(BaseModel):
    """Message format for inter-process communication"""
    type: IpcMessageType
    request_id: str
    payload: Optional[Dict[str, Any]] = None
    timestamp: int = Field(default_factory=lambda: int(time.time() * 1000))
