from typing import Literal, Dict, Any
from pydantic import model_validator
from ...common import CommonModelComponentConfig, ModelTaskType, ModelProvider

class CommonPoseDetectionModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.POSE_DETECTION]

    @model_validator(mode="before")
    def inject_default_model(cls, values: Dict[str, Any]):
        if values.get("model") is None:
            values["model"] = { "provider": ModelProvider.LOCAL, "path": "__default__" }
        return values
