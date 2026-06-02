from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field, model_validator
from .types import ControllerAdapterType
from ..common import CommonControllerAdapterConfig

class WebSocketConfig(BaseModel):
    path: str = Field(default="/ws", description="WebSocket endpoint path")
    max_connection_count: Optional[int] = Field(default=None, description="Maximum concurrent WebSocket connections (best-effort)")
    ping_interval: Union[str, int, float] = Field(default="30s", description="Server-side ping interval (e.g. '30s'). '0s' to disable.")
    ping_timeout: Union[str, int, float] = Field(default="10s", description="Ping timeout (e.g. '10s').")

class HttpServerControllerAdapterConfig(CommonControllerAdapterConfig):
    type: Literal[ControllerAdapterType.HTTP_SERVER]
    origins: Optional[str] = Field(default="*", description="CORS allowed origins, specified as a comma-separated string")
    websocket: Union[bool, WebSocketConfig] = Field(default_factory=WebSocketConfig, description="WebSocket configuration. false to disable, true or omit for default config.")

    @model_validator(mode="before")
    def inflate_websocket(cls, values: Dict[str, Any]):
        websocket = values.get("websocket")
        if websocket is True:
            values["websocket"] = {}
        return values
