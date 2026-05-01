from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import WebSocketClientActionConfig
from .common import ComponentType, CommonComponentConfig

class WebSocketClientComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.WEBSOCKET_CLIENT]
    base_url: str = Field(..., description="Base URL of the external WebSocket server (e.g. ws://host:port or wss://host:port).")
    params: Dict[str, Any] = Field(default_factory=dict, description="Default query parameters to include in all WebSocket connection URLs.")
    headers: Dict[str, str] = Field(default_factory=dict, description="Headers to be included in all outgoing WebSocket handshake requests.")
    ping_interval: Optional[str] = Field(default=None, description="WebSocket ping interval (e.g. '20s'). Omit to use library default.")
    ping_timeout: Optional[str] = Field(default=None, description="WebSocket ping timeout (e.g. '10s'). Omit to use library default.")
    actions: List[WebSocketClientActionConfig] = Field(default_factory=list)
