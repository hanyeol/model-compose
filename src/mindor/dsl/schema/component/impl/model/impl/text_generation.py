from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.action import TextGenerationModelActionConfig
from .common import CommonModelComponentConfig, ModelTaskType

class TextGenerationModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.TEXT_GENERATION]
    actions: Dict[str, TextGenerationModelActionConfig] = Field(default_factory=dict)

    @model_validator(mode="before")
    def inflate_single_action(cls, values: Dict[str, Any]):
        if "actions" not in values:
            action_keys = set(TextGenerationModelActionConfig.model_fields.keys())
            if any(k in values for k in action_keys):
                values["actions"] = { "__default__": { k: values.pop(k) for k in action_keys if k in values } }
        return values
