from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from .common import CommonActionConfig

class WebSocketReceiveFormat(str, Enum):
    JSON   = "json"
    TEXT   = "text"
    BINARY = "binary"

class WebSocketReceiveConfig(BaseModel):
    format: WebSocketReceiveFormat = Field(default=WebSocketReceiveFormat.JSON, description="Expected encoding of received WebSocket frames.")
    collect: Union[bool, str] = Field(default=False, description="Whether all received frames are collected into a single response.")
    streaming: Union[bool, str] = Field(default=False, description="Whether received frames are emitted incrementally as a chunked stream.")
    timeout: Optional[Union[str, int, float]] = Field(default=None, description="Maximum time to wait for each frame before failing.")

class WebSocketServerActionConfig(CommonActionConfig):
    path: Optional[str] = Field(default=None, description="WebSocket path exposed by this action, overriding the component's base path.")
    params: Dict[str, Any] = Field(default_factory=dict, description="Expected query parameters on the WebSocket URL.")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP headers accepted on the WebSocket handshake.")
    message: Optional[Any] = Field(default=None, description="Message sent to the client after the WebSocket connection is established.")
    receive: WebSocketReceiveConfig = Field(default_factory=WebSocketReceiveConfig, description="Settings that control how incoming WebSocket messages are received.")
