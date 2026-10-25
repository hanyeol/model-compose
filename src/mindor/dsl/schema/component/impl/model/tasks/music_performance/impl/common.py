from typing import Literal, Dict, Any
from pydantic import model_validator
from mindor.dsl.schema.action import MusicPerformanceActionMethod
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonMusicPerformanceModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.MUSIC_PERFORMANCE]

    @model_validator(mode="before")
    def inject_default_action_method(cls, values: Dict[str, Any]):
        actions = values.get("actions")
        if actions is None:
            action = values.get("action")
            actions = [ action ] if action else []
        for action in actions:
            if isinstance(action, dict) and "method" not in action:
                action["method"] = MusicPerformanceActionMethod.RENDER
        return values
