from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field, model_validator
from ...common import CommonComponentConfig, ComponentType

class ShellDriver(str, Enum):
    LOCAL = "local"
    SSH   = "ssh"

class ShellManageScripts(BaseModel):
    install: Optional[List[List[str]]] = Field(default=None, description="Commands run to install dependencies for shell actions.")
    clean: Optional[List[List[str]]] = Field(default=None, description="Commands run to clean up the shell execution environment.")

    @model_validator(mode="before")
    def normalize_scripts(cls, values):
        for key in [ "install", "clean" ]:
            script = values.get(key)
            if script and isinstance(script, list) and all(isinstance(token, str) for token in script):
                values[key] = [ script ]
        return values

class ShellManageConfig(BaseModel):
    scripts: ShellManageScripts = Field(..., description="Shell scripts that install dependencies and clean up the environment.")
    working_dir: Optional[str] = Field(default=None, description="Working directory in which the scripts run.")
    env: Dict[str, str] = Field(default_factory=dict, description="Environment variables exported when the scripts run.")

    @model_validator(mode="before")
    def inflate_single_script(cls, values: Dict[str, Any]):
        if "scripts" not in values:
            values["scripts"] = { key: values.pop(key) for key in ShellManageScripts.model_fields.keys() if key in values }
        return values

class CommonShellComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.SHELL]
    driver: ShellDriver = Field(default=ShellDriver.LOCAL, description="Backend implementation used to execute shell commands.")
    manage: ShellManageConfig = Field(default_factory=ShellManageConfig, description="Lifecycle scripts and environment for this shell component.")
    base_dir: Optional[str] = Field(default=None, description="Base working directory for every action in this component.")
    env: Dict[str, str] = Field(default_factory=dict, description="Environment variables exported for every action in this component.")

    @model_validator(mode="before")
    def inflate_single_script(cls, values: Dict[str, Any]):
        if "manage" not in values:
            values["manage"] = { key: values.pop(key) for key in ShellManageScripts.model_fields.keys() if key in values }
        return values
