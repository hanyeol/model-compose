from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.action import WebSocketServerActionConfig
from .common import ComponentType, CommonComponentConfig

class WebSocketServerManageScripts(BaseModel):
    install: Optional[List[List[str]]] = Field(default=None, description="Commands run to install the server's dependencies.")
    build: Optional[List[List[str]]] = Field(default=None, description="Commands run to build the server.")
    clean: Optional[List[List[str]]] = Field(default=None, description="Commands run to clean the server's environment.")
    start: Optional[List[str]] = Field(default=None, description="Command that starts the server process.")

    @model_validator(mode="before")
    def normalize_scripts(cls, values):
        for key in [ "install", "build", "clean" ]:
            script = values.get(key)
            if script and isinstance(script, list) and all(isinstance(token, str) for token in script):
                values[key] = [ script ]
        return values

class WebSocketServerManageConfig(BaseModel):
    scripts: WebSocketServerManageScripts = Field(..., description="Shell scripts that install, build, clean, and start the server.")
    working_dir: Optional[str] = Field(default=None, description="Working directory in which the scripts run.")
    env: Dict[str, str] = Field(default_factory=dict, description="Environment variables exported when the scripts run.")

    @model_validator(mode="before")
    def inflate_single_script(cls, values: Dict[str, Any]):
        if "scripts" not in values:
            values["scripts"] = { key: values.pop(key) for key in WebSocketServerManageScripts.model_fields.keys() if key in values }
        return values

class WebSocketServerComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.WEBSOCKET_SERVER]
    manage: WebSocketServerManageConfig = Field(default_factory=WebSocketServerManageConfig, description="Lifecycle scripts and environment for the managed WebSocket server.")
    port: int = Field(default=3000, ge=1, le=65535, description="TCP port the WebSocket server listens on.")
    base_path: Optional[str] = Field(default=None, description="URL path prefix under which this server's routes are exposed.")
    params: Dict[str, Any] = Field(default_factory=dict, description="Query parameters appended to every WebSocket connection URL.")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP headers sent with every WebSocket handshake.")
    ping_interval: Optional[Union[str, int, float]] = Field(default=None, description="Interval between WebSocket keepalive pings, as a duration string or seconds.")
    ping_timeout: Optional[Union[str, int, float]] = Field(default=None, description="Maximum seconds to wait for a ping response before dropping the connection.")
    actions: List[WebSocketServerActionConfig] = Field(default_factory=list)

    @model_validator(mode="before")
    def inflate_single_script(cls, values: Dict[str, Any]):
        if "manage" not in values:
            values["manage"] = { key: values.pop(key) for key in WebSocketServerManageScripts.model_fields.keys() if key in values }
        return values
