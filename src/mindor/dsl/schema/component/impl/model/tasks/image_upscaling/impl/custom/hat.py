from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import HatImageUpscalingModelActionConfig
from ..common import CommonImageUpscalingModelComponentConfig
from .common import ImageUpscalingModelFamily
from ....common import ModelDriverType

class HatImageUpscalingModelComponentConfig(CommonImageUpscalingModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[ImageUpscalingModelFamily.HAT]
    actions: List[HatImageUpscalingModelActionConfig] = Field(default_factory=list, description="Actions this image upscaling component exposes to workflows.")
