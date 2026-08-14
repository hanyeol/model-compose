from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import WebSocketClientActionConfig
from .common import ComponentType, CommonComponentConfig

class WebSocketClientComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.WEBSOCKET_CLIENT]
    base_url: str = Field(..., description="Base URL of the WebSocket endpoint (e.g., ws://host:port or wss://host:port).")
    params: Dict[str, Any] = Field(default_factory=dict, description="Query parameters appended to every WebSocket connection URL.")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP headers sent with every WebSocket handshake.")
    ping_interval: Optional[Union[str, int, float]] = Field(default=None, description="Interval between WebSocket keepalive pings, as a duration string or seconds.")
    ping_timeout: Optional[Union[str, int, float]] = Field(default=None, description="Maximum seconds to wait for a ping response before dropping the connection.")
    actions: List[WebSocketClientActionConfig] = Field(default_factory=list)
