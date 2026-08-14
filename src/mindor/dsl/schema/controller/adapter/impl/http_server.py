from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field, model_validator
from .types import ControllerAdapterType
from ..common import CommonControllerAdapterConfig

class WebSocketConfig(BaseModel):
    path: str = Field(default="/ws", description="URL path where the WebSocket endpoint is served.")
    max_connection_count: Optional[int] = Field(default=None, description="Maximum concurrent WebSocket connections, enforced best-effort.")
    ping_interval: Union[str, int, float] = Field(default="30s", description="Interval between server-side keepalive pings; '0s' disables pings.")
    ping_timeout: Union[str, int, float] = Field(default="10s", description="Maximum seconds to wait for a ping response before closing the connection.")

class HttpServerControllerAdapterConfig(CommonControllerAdapterConfig):
    type: Literal[ControllerAdapterType.HTTP_SERVER]
    origins: Optional[str] = Field(default="*", description="Comma-separated list of allowed CORS origins.")
    websocket: Union[bool, WebSocketConfig] = Field(default_factory=WebSocketConfig, description="WebSocket settings; false disables the endpoint, true uses defaults.")

    @model_validator(mode="before")
    def inflate_websocket(cls, values: Dict[str, Any]):
        websocket = values.get("websocket")
        if websocket is True:
            values["websocket"] = {}
        return values
