from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import WebSocketClientActionConfig
from .common import ComponentType, CommonComponentConfig

class WebSocketClientComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.WEBSOCKET_CLIENT]
    base_url: str = Field(..., description="Base URL of the WebSocket server (e.g. ws://host:port or wss://host:port).")
    params: Dict[str, Any] = Field(default_factory=dict, description="Default query parameters for all connection URLs.")
    headers: Dict[str, str] = Field(default_factory=dict, description="Headers included in all outgoing WebSocket handshake requests.")
    ping_interval: Optional[Union[str, int, float]] = Field(default=None, description="WebSocket ping interval (e.g. '20s').")
    ping_timeout: Optional[Union[str, int, float]] = Field(default=None, description="WebSocket ping timeout (e.g. '10s').")
    actions: List[WebSocketClientActionConfig] = Field(default_factory=list)
