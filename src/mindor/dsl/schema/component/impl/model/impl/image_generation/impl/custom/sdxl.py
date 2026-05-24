from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import SdxlImageGenerationModelActionConfig
from ..common import CommonImageGenerationModelComponentConfig
from ....common import ModelDriver
from .custom import CustomImageGenerationModelFamily

class SdxlImageGenerationModelComponentConfig(CommonImageGenerationModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[CustomImageGenerationModelFamily.SDXL]
    actions: List[SdxlImageGenerationModelActionConfig] = Field(default_factory=list)
