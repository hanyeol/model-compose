from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.action import ModelActionConfig
from mindor.dsl.utils.annotation import get_model_union_keys
from ...common import CommonComponentConfig, ComponentType
from .types import ModelTaskType

class CommonModelComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.MODEL]
    task: ModelTaskType = Field(..., description="")
    model: str = Field(..., description="")
    device: str = Field(default="cpu", description="Computation device to use.")
    cache_dir: Optional[str] = Field(default=None, description="")
    actions: Dict[str, ModelActionConfig] = Field(default_factory=dict)

    @model_validator(mode="before")
    def inflate_single_action(cls, values: Dict[str, Any]):
        if "actions" not in values:
            action_keys = set(get_model_union_keys(ModelActionConfig))
            if any(k in values for k in action_keys):
                values["actions"] = { "__default__": { k: values.pop(k) for k in action_keys if k in values } }
        return values
