from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.action import ShellActionConfig
from .common import ComponentType, CommonComponentConfig

class ShellManageScripts(BaseModel):
    install: Optional[List[List[str]]] = Field(default=None, description="One or more scripts to install dependencies.")
    clean: Optional[List[List[str]]] = Field(default=None, description="One or more scripts to clean up the execution environment.")

    @model_validator(mode="before")
    def normalize_scripts(cls, values):
        for key in [ "install", "clean" ]:
            script = values.get(key)
            if script and isinstance(script, list) and all(isinstance(token, str) for token in script):
                values[key] = [ script ]
        return values

class ShellManageConfig(BaseModel):
    scripts: ShellManageScripts = Field(..., description="Shell scripts used to install dependencies and clean up the environment.")
    working_dir: Optional[str] = Field(default=None, description="Working directory for the scripts.")
    env: Dict[str, str] = Field(default_factory=dict, description="Environment variables to set when executing the scripts.")

    @model_validator(mode="before")
    def inflate_single_script(cls, values: Dict[str, Any]):
        if "scripts" not in values:
            values["scripts"] = { key: values.pop(key) for key in ShellManageScripts.model_fields.keys() if key in values }
        return values

class ShellComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.SHELL]
    manage: ShellManageConfig = Field(default_factory=ShellManageConfig, description="Configuration for scripts and environment setup related to this shell component.")
    base_dir: Optional[str] = Field(default=None, description="Base working directory for all actions in this component.")
    env: Dict[str, str] = Field(default_factory=dict, description="Environment variables to set for all actions in this component.")
    actions: List[ShellActionConfig] = Field(default_factory=list)

    @model_validator(mode="before")
    def inflate_single_script(cls, values: Dict[str, Any]):
        if "manage" not in values:
            values["manage"] = { key: values.pop(key) for key in ShellManageScripts.model_fields.keys() if key in values }
        return values
