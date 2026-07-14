from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from .common import CommonActionConfig

class WebSocketReceiveFormat(str, Enum):
    JSON   = "json"
    TEXT   = "text"
    BINARY = "binary"

class WebSocketReceiveConfig(BaseModel):
    format: WebSocketReceiveFormat = Field(default=WebSocketReceiveFormat.JSON, description="Expected format of received WebSocket frames.")
    collect: Union[bool, str] = Field(default=False, description="Collect all frames into a single response.")
    streaming: Union[bool, str] = Field(default=False, description="Hand received frames to subsequent jobs as a chunked stream.")
    timeout: Optional[Union[str, int, float]] = Field(default=None, description="Receive timeout per frame (e.g. '5s', '1m').")

class WebSocketServerActionConfig(CommonActionConfig):
    path: Optional[str] = Field(default=None, description="WebSocket endpoint path. Overrides the component-level base_path.")
    params: Dict[str, Any] = Field(default_factory=dict, description="Query parameters for the WebSocket URL.")
    headers: Dict[str, str] = Field(default_factory=dict, description="Additional headers for the WebSocket handshake.")
    message: Optional[Any] = Field(default=None, description="Message to send after connecting.")
    receive: WebSocketReceiveConfig = Field(default_factory=WebSocketReceiveConfig, description="Settings for receiving WebSocket messages.")
