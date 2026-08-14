from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .common import CommonActionConfig
from .websocket_server import WebSocketReceiveConfig

class WebSocketClientActionConfig(CommonActionConfig):
    path: Optional[str] = Field(default=None, description="WebSocket path appended to the component's base URL.")
    params: Dict[str, Any] = Field(default_factory=dict, description="Query parameters appended to the WebSocket URL.")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP headers sent with the WebSocket handshake.")
    message: Optional[Any] = Field(default=None, description="Message sent after the WebSocket connection is established.")
    receive: WebSocketReceiveConfig = Field(default_factory=WebSocketReceiveConfig, description="Settings that control how incoming WebSocket messages are received.")
