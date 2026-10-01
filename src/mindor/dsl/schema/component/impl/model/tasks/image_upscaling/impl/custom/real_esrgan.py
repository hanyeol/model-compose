from typing import Union, Literal, List
from pydantic import Field
from mindor.dsl.schema.action import RealEsrganImageUpscalingModelActionConfig
from ..common import CommonImageUpscalingModelComponentConfig
from .common import ImageUpscalingModelFamily
from ....common import ModelDriverType

class RealEsrganImageUpscalingModelComponentConfig(CommonImageUpscalingModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[ImageUpscalingModelFamily.REAL_ESRGAN]
    scale: Union[int, str] = Field(default=2, description="Multiplier applied to output resolution.")
    actions: List[RealEsrganImageUpscalingModelActionConfig] = Field(default_factory=list, description="Actions this image upscaling component exposes to workflows.")
