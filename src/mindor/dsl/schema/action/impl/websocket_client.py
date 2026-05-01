from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .common import CommonActionConfig
from .websocket_server import WebSocketReceiveConfig

class WebSocketClientActionConfig(CommonActionConfig):
    path: Optional[str] = Field(default=None, description="WebSocket endpoint path to append to the component base_url.")
    params: Dict[str, Any] = Field(default_factory=dict, description="Query parameters to include in the WebSocket URL.")
    headers: Dict[str, str] = Field(default_factory=dict, description="Additional headers for the WebSocket handshake.")
    message: Optional[Any] = Field(default=None, description="Message to send after connecting. Dict/List will be JSON-encoded, bytes sent as binary, str sent as text.")
    receive: WebSocketReceiveConfig = Field(default_factory=WebSocketReceiveConfig, description="Configuration for receiving WebSocket messages.")
