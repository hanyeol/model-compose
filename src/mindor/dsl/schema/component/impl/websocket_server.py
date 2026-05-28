from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.action import WebSocketServerActionConfig
from .common import ComponentType, CommonComponentConfig

class WebSocketServerManageScripts(BaseModel):
    install: Optional[List[List[str]]] = Field(default=None, description="One or more scripts to install dependencies.")
    build: Optional[List[List[str]]] = Field(default=None, description="One or more scripts to build the server.")
    clean: Optional[List[List[str]]] = Field(default=None, description="One or more scripts to clean the server environment.")
    start: Optional[List[str]] = Field(default=None, description="Script to start the server.")

    @model_validator(mode="before")
    def normalize_scripts(cls, values):
        for key in [ "install", "build", "clean" ]:
            script = values.get(key)
            if script and isinstance(script, list) and all(isinstance(token, str) for token in script):
                values[key] = [ script ]
        return values

class WebSocketServerManageConfig(BaseModel):
    scripts: WebSocketServerManageScripts = Field(..., description="Shell scripts used to install, build, clean, and start the server.")
    working_dir: Optional[str] = Field(default=None, description="Working directory for the scripts.")
    env: Dict[str, str] = Field(default_factory=dict, description="Environment variables to set when executing the scripts.")

    @model_validator(mode="before")
    def inflate_single_script(cls, values: Dict[str, Any]):
        if "scripts" not in values:
            values["scripts"] = { key: values.pop(key) for key in WebSocketServerManageScripts.model_fields.keys() if key in values }
        return values

class WebSocketServerComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.WEBSOCKET_SERVER]
    manage: WebSocketServerManageConfig = Field(default_factory=WebSocketServerManageConfig, description="Configuration used to manage the WebSocket server lifecycle.")
    port: int = Field(default=3000, ge=1, le=65535, description="Port on which the WebSocket server will listen for incoming connections.")
    base_path: Optional[str] = Field(default=None, description="Base path to prefix all WebSocket routes exposed by this component.")
    params: Dict[str, Any] = Field(default_factory=dict, description="Default query parameters to include in all WebSocket connection URLs.")
    headers: Dict[str, str] = Field(default_factory=dict, description="Headers to be included in all outgoing WebSocket handshake requests.")
    ping_interval: Optional[Union[str, int, float]] = Field(default=None, description="WebSocket ping interval (e.g. '20s'). Omit to use library default.")
    ping_timeout: Optional[Union[str, int, float]] = Field(default=None, description="WebSocket ping timeout (e.g. '10s'). Omit to use library default.")
    actions: List[WebSocketServerActionConfig] = Field(default_factory=list)

    @model_validator(mode="before")
    def inflate_single_script(cls, values: Dict[str, Any]):
        if "manage" not in values:
            values["manage"] = { key: values.pop(key) for key in WebSocketServerManageScripts.model_fields.keys() if key in values }
        return values
