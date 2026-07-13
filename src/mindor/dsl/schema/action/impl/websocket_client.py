from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .common import CommonActionConfig
from .websocket_server import WebSocketReceiveConfig

class WebSocketClientActionConfig(CommonActionConfig):
    path: Optional[str] = Field(default=None, description="WebSocket endpoint path appended to the component base_url.")
    params: Dict[str, Any] = Field(default_factory=dict, description="Query parameters for the WebSocket URL.")
    headers: Dict[str, str] = Field(default_factory=dict, description="Additional headers for the WebSocket handshake.")
    message: Optional[Any] = Field(default=None, description="Message to send after connecting.")
    receive: WebSocketReceiveConfig = Field(default_factory=WebSocketReceiveConfig, description="Settings for receiving WebSocket messages.")
