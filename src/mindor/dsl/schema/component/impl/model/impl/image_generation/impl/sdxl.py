from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import SdxlImageGenerationModelActionConfig
from .common import CommonImageGenerationModelComponentConfig, ImageGenerationModelFamily

class SdxlImageGenerationModelComponentConfig(CommonImageGenerationModelComponentConfig):
    family: Literal[ImageGenerationModelFamily.SDXL]
    actions: List[SdxlImageGenerationModelActionConfig] = Field(default_factory=list)
