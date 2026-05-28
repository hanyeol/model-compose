from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import SdxlImageGenerationModelActionConfig
from ...common import CommonImageGenerationModelComponentConfig
from .....common import ModelDriver
from .common import ImageGenerationModelFamily

class SdxlImageGenerationModelComponentConfig(CommonImageGenerationModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[ImageGenerationModelFamily.SDXL]
    actions: List[SdxlImageGenerationModelActionConfig] = Field(default_factory=list)
