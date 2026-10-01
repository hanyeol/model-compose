from typing import Union, Literal, List
from pydantic import Field
from mindor.dsl.schema.action import EsrganImageUpscalingModelActionConfig
from ..common import CommonImageUpscalingModelComponentConfig
from .common import ImageUpscalingModelFamily
from ....common import ModelDriverType

class EsrganImageUpscalingModelComponentConfig(CommonImageUpscalingModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[ImageUpscalingModelFamily.ESRGAN]
    scale: Union[int, str] = Field(default=2, description="Multiplier applied to output resolution.")
    actions: List[EsrganImageUpscalingModelActionConfig] = Field(default_factory=list, description="Actions this image upscaling component exposes to workflows.")
