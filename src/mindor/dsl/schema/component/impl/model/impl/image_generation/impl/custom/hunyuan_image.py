from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import HunyuanImageGenerationModelActionConfig
from ..common import CommonImageGenerationModelComponentConfig
from ....common import ModelDriver
from .custom import CustomImageGenerationModelFamily

class HunyuanImageGenerationModelComponentConfig(CommonImageGenerationModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[CustomImageGenerationModelFamily.HUNYUAN_IMAGE]
    actions: List[HunyuanImageGenerationModelActionConfig] = Field(default_factory=list)
