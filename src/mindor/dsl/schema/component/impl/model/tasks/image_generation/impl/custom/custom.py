from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import ImageGenerationModelActionConfig
from ..common import CommonImageGenerationModelComponentConfig
from .common import ImageGenerationModelFamily
from ....common import ModelDriverType

class CustomImageGenerationModelComponentConfig(CommonImageGenerationModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: ImageGenerationModelFamily = Field(..., description="Model family selecting the custom image generation implementation.")
    actions: List[ImageGenerationModelActionConfig] = Field(default_factory=list, description="Actions this image generation component exposes to workflows.")
