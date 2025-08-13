from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.action import HttpServerActionConfig
from .common import ComponentType, CommonComponentConfig

class HttpServerManageScripts(BaseModel):
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

class HttpServerManageConfig(BaseModel):
    scripts: HttpServerManageScripts = Field(..., description="Shell scripts used to install, build, clean, and start the server.")
    working_dir: Optional[str] = Field(default=None, description="Working directory for the scripts.")
    env: Dict[str, str] = Field(default_factory=dict, description="Environment variables to set when executing the scripts.")

    @model_validator(mode="before")
    def inflate_single_script(cls, values: Dict[str, Any]):
        if "scripts" not in values:
            values["scripts"] = { key: values.pop(key) for key in HttpServerManageScripts.model_fields.keys() if key in values }
        return values

class HttpServerComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.HTTP_SERVER]
    manage: HttpServerManageConfig = Field(default_factory=HttpServerManageConfig, description="Configuration used to manage the HTTP server lifecycle.")
    port: int = Field(default=8000, ge=1, le=65535, description="Port on which the HTTP server will listen for incoming requests.")
    base_path: Optional[str] = Field(default=None, description="Base path to prefix all HTTP routes exposed by this component.")
    headers: Dict[str, Any] = Field(default_factory=dict, description="Headers to be included in all outgoing HTTP requests.")
    actions: List[HttpServerActionConfig] = Field(default_factory=list)

    @model_validator(mode="before")
    def inflate_single_script(cls, values: Dict[str, Any]):
        if "manage" not in values:
            values["manage"] = { key: values.pop(key) for key in HttpServerManageScripts.model_fields.keys() if key in values }
        return values

    @model_validator(mode="before")
    def inflate_single_action(cls, values: Dict[str, Any]):
        if "actions" not in values:
            action_keys = set(HttpServerActionConfig.model_fields.keys()) - set(CommonComponentConfig.model_fields.keys())
            if any(k in values for k in action_keys):
                values["actions"] = [ { k: values.pop(k) for k in action_keys if k in values } ]
        return values
