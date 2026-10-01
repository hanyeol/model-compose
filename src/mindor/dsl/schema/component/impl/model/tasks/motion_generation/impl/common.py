from typing import Literal, Dict, Any
from pydantic import model_validator
from mindor.dsl.schema.action import MotionGenerationActionMethod
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonMotionGenerationModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.MOTION_GENERATION]

    @model_validator(mode="before")
    def inject_default_action_method(cls, values: Dict[str, Any]):
        actions = values.get("actions")
        if actions is None:
            action = values.get("action")
            actions = [ action ] if action else []
        for action in actions:
            if isinstance(action, dict) and "method" not in action:
                action["method"] = MotionGenerationActionMethod.GENERATE
        return values
