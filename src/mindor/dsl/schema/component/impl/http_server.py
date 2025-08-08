from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.action import HttpServerActionConfig
from .common import ComponentType, CommonComponentConfig

class HttpServerCommands(BaseModel):
    install: Optional[List[List[str]]] = Field(default=None, description="One or more commands to install dependencies.")
    build: Optional[List[List[str]]] = Field(default=None, description="One or more commands to build the server.")
    start: Optional[List[str]] = Field(default=None, description="Command to start the server.")

    @model_validator(mode="before")
    def normalize_commands(cls, values):
        for key in [ "install", "build" ]:
            command = values.get(key)
            if command and isinstance(command, list) and all(isinstance(token, str) for token in command):
                values[key] = [ command ]
        return values

class HttpServerComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.HTTP_SERVER]
    commands: HttpServerCommands = Field(..., description="Shell commands used to install, build, and start the server.")
    working_dir: Optional[str] = Field(default=None, description="Working directory for the commands.")
    env: Dict[str, str] = Field(default_factory=dict, description="Environment variables to set when executing the commands.")
    port: int = Field(default=8000, ge=1, le=65535, description="Port on which the server will listen.")
    base_path: Optional[str] = Field(default=None, description="Base path to prefix all HTTP routes exposed by this component.")
    headers: Dict[str, Any] = Field(default_factory=dict, description="Headers to be included in all outgoing HTTP requests.")
    actions: Dict[str, HttpServerActionConfig] = Field(default_factory=dict)

    @model_validator(mode="before")
    def inflate_single_command(cls, values: Dict[str, Any]):
        if "commands" not in values:
            if "command" in values:
                values["commands"] = { "start": values.pop("command") }
        return values

    @model_validator(mode="before")
    def inflate_single_action(cls, values: Dict[str, Any]):
        if "actions" not in values:
            action_keys = set(HttpServerActionConfig.model_fields.keys())
            if any(k in values for k in action_keys):
                values["actions"] = { "__default__": { k: values.pop(k) for k in action_keys if k in values } }
        return values
