from typing import Literal, Optional
from enum import Enum
from pydantic import Field
from ...common import CommonModelComponentConfig, ModelTaskType, ModelDriver

class ImageGenerationModelFamily(str, Enum):
    SDXL          = "sdxl"
    FLUX          = "flux"
    HUNYUAN_IMAGE = "hunyuan-image"

class CommonImageGenerationModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.IMAGE_GENERATION]
    driver: ModelDriver = Field(default=ModelDriver.CUSTOM)
    family: ImageGenerationModelFamily = Field(..., description="Model family.")
    version: Optional[str] = Field(default=None, description="")
