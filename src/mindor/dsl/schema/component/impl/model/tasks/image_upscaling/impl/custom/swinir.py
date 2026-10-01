from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import SwinIRImageUpscalingModelActionConfig
from ..common import CommonImageUpscalingModelComponentConfig
from .common import ImageUpscalingModelFamily
from ....common import ModelDriverType

class SwinIRImageUpscalingModelComponentConfig(CommonImageUpscalingModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[ImageUpscalingModelFamily.SWINIR]
    actions: List[SwinIRImageUpscalingModelActionConfig] = Field(default_factory=list, description="Actions this image upscaling component exposes to workflows.")
