from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.action import McpServerActionConfig
from .common import ComponentType, CommonComponentConfig

class McpServerCommands(BaseModel):
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

class McpServerComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.MCP_SERVER]
    commands: McpServerCommands = Field(..., description="")
    working_dir: Optional[str] = Field(default=None, description="Working directory for the commands.")
    env: Dict[str, str] = Field(default_factory=dict, description="Environment variables to set when executing the commands.")
    port: int = Field(default=8000, ge=1, le=65535, description="")
    base_path: Optional[str] = Field(default=None, description="")
    actions: Dict[str, McpServerActionConfig] = Field(default_factory=dict)
