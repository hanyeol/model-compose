from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.action import ShellActionConfig
from .common import ComponentType, CommonComponentConfig

class ShellComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.SHELL]
    base_dir: Optional[str] = Field(default=None, description="Base working directory for all actions in this component.")
    env: Optional[Dict[str, str]] = Field(default_factory=dict, description="Environment variables to set for all actions in this component.")
    actions: Optional[Dict[str, ShellActionConfig]] = Field(default_factory=dict, description="Shell actions mapped by an identifier.")

    @model_validator(mode="before")
    def inflate_single_action(cls, values: Dict[str, Any]):
        if "actions" not in values:
            action_keys = set(ShellActionConfig.model_fields.keys())
            if any(k in values for k in action_keys):
                values["actions"] = { "__default__": { k: values.pop(k) for k in action_keys if k in values } }
        return values
