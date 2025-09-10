from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Type, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from ...common import CommonModelComponentConfig, ModelTaskType, ModelDriver

class ImageUpscaleModelArchitecture(str, Enum):
    ESRGAN      = "esrgan"
    REAL_ESRGAN = "real-esrgan"
    LDSR        = "ldsr"
    SWINIR      = "swinir"

class CommonImageUpscaleModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.IMAGE_UPSCALE]
    driver: ModelDriver = Field(default=ModelDriver.CUSTOM)
    architecture: ImageUpscaleModelArchitecture = Field(..., description="Model architecture.")

    @model_validator(mode="before")
    def inflate_single_action(cls, values: Dict[str, Any]):
        if "actions" not in values:
            action_keys = set(cls._get_action_class().model_fields.keys()) - set(CommonModelComponentConfig.model_fields.keys())
            if any(k in values for k in action_keys):
                values["actions"] = [ { k: values.pop(k) for k in action_keys if k in values } ]
        return values

    @classmethod
    def _get_action_class(cls) -> Type[BaseModel]:
        return None
