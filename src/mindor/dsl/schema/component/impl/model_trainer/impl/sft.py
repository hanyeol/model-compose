from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.action import SftnModelTrainerActionConfig
from .common import CommonModelTrainerComponentConfig, TrainingTaskType

class SftModelTrainerComponentConfig(CommonModelTrainerComponentConfig):
    task: Literal[TrainingTaskType.SFT]
    actions: List[SftnModelTrainerActionConfig] = Field(default_factory=list)

    @model_validator(mode="before")
    def inflate_single_action(cls, values: Dict[str, Any]):
        if "actions" not in values:
            action_keys = set(SftnModelTrainerActionConfig.model_fields.keys()) - set(CommonModelTrainerComponentConfig.model_fields.keys())
            if any(k in values for k in action_keys):
                values["actions"] = [ { k: values.pop(k) for k in action_keys if k in values } ]
        return values
