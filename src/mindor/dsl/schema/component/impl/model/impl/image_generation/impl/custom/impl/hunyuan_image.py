from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import HunyuanImageGenerationModelActionConfig
from ...common import CommonImageGenerationModelComponentConfig
from .....common import ModelDriver
from .common import ImageGenerationModelFamily

class HunyuanImageGenerationModelComponentConfig(CommonImageGenerationModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[ImageGenerationModelFamily.HUNYUAN_IMAGE]
    actions: List[HunyuanImageGenerationModelActionConfig] = Field(default_factory=list)
