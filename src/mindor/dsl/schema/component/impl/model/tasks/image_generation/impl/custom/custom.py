from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import ImageGenerationModelActionConfig
from ..common import CommonImageGenerationModelComponentConfig
from .impl.common import ImageGenerationModelFamily
from ....common import ModelDriver

class CustomImageGenerationModelComponentConfig(CommonImageGenerationModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: ImageGenerationModelFamily = Field(..., description="Model family.")
    actions: List[ImageGenerationModelActionConfig] = Field(default_factory=list)
