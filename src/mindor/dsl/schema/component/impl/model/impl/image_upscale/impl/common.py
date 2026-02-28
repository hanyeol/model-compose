from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonModelComponentConfig, ModelTaskType, ModelDriver

class ImageUpscaleModelFamily(str, Enum):
    ESRGAN      = "esrgan"
    REAL_ESRGAN = "real-esrgan"
    LDSR        = "ldsr"
    SWINIR      = "swinir"

class CommonImageUpscaleModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.IMAGE_UPSCALE]
    driver: ModelDriver = Field(default=ModelDriver.CUSTOM)
    family: ImageUpscaleModelFamily = Field(..., description="Model family.")
