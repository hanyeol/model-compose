from typing import Literal, Optional, Dict, Any
from pydantic import Field, model_validator
from mindor.dsl.schema.action import ImageGenerationActionMethod
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonImageGenerationModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.IMAGE_GENERATION]
    version: Optional[str] = Field(default=None, description="Model version or variant.")

    @model_validator(mode="before")
    def inject_default_action_method(cls, values: Dict[str, Any]):
        for action in values.get("actions") or []:
            if isinstance(action, dict) and "method" not in action:
                action["method"] = ImageGenerationActionMethod.GENERATE
        return values
