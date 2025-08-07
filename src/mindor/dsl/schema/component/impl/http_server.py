from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.action import HttpServerActionConfig
from .common import ComponentType, CommonComponentConfig

class HttpServerCommands(BaseModel):
    install: Optional[List[str]] = Field(default=None, description="")
    build: Optional[List[str]] = Field(default=None, description="")
    start: Optional[List[str]] = Field(default=None, description="")

class HttpServerComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.HTTP_SERVER]
    commands: HttpServerCommands = Field(..., description="")
    working_dir: Optional[str] = Field(default=None, description="Working directory for the commands.")
    env: Dict[str, str] = Field(default_factory=dict, description="Environment variables to set when executing the commands.")
    port: int = Field(default=8000, ge=1, le=65535, description="")
    base_path: Optional[str] = Field(default=None, description="")
    headers: Dict[str, Any] = Field(default_factory=dict, description="")
    actions: Dict[str, HttpServerActionConfig] = Field(default_factory=dict, description="")

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
