from typing import Literal, Dict, Any
from pydantic import model_validator
from mindor.dsl.schema.action import TextToSpeechActionMethod
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonTextToSpeechModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.TEXT_TO_SPEECH]

    @model_validator(mode="before")
    def inject_default_action_method(cls, values: Dict[str, Any]):
        for action in values.get("actions") or []:
            if isinstance(action, dict) and "method" not in action:
                action["method"] = TextToSpeechActionMethod.GENERATE
        return values
