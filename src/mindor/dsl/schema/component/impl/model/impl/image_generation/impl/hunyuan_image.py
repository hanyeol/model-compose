from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import HunyuanImageGenerationModelActionConfig
from .common import CommonImageGenerationModelComponentConfig, ImageGenerationModelFamily

class HunyuanImageGenerationModelComponentConfig(CommonImageGenerationModelComponentConfig):
    family: Literal[ImageGenerationModelFamily.HUNYUAN_IMAGE]
    actions: List[HunyuanImageGenerationModelActionConfig] = Field(default_factory=list)
