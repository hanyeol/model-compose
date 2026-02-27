from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.action import TextToSpeechModelActionConfig
from mindor.dsl.utils.annotation import get_model_union_keys
from .common import CommonTextToSpeechModelComponentConfig, TextToSpeechModelFamily

class QwenTextToSpeechModelComponentConfig(CommonTextToSpeechModelComponentConfig):
    family: Literal[TextToSpeechModelFamily.QWEN]
    actions: List[TextToSpeechModelActionConfig] = Field(default_factory=list)

    @model_validator(mode="before")
    def inflate_single_action(cls, values: Dict[str, Any]):
        if "actions" not in values:
            action_keys = set(get_model_union_keys(TextToSpeechModelActionConfig)) - set(CommonTextToSpeechModelComponentConfig.model_fields.keys())
            if any(k in values for k in action_keys):
                values["actions"] = [ { k: values.pop(k) for k in action_keys if k in values } ]
        return values
