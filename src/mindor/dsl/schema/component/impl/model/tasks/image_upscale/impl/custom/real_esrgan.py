from typing import Union, Literal, List
from pydantic import Field
from mindor.dsl.schema.action import RealEsrganImageUpscaleModelActionConfig
from ..common import CommonImageUpscaleModelComponentConfig
from .common import ImageUpscaleModelFamily
from ....common import ModelDriverType

class RealEsrganImageUpscaleModelComponentConfig(CommonImageUpscaleModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[ImageUpscaleModelFamily.REAL_ESRGAN]
    scale: Union[int, str] = Field(default=2, description="Multiplier applied to output resolution.")
    actions: List[RealEsrganImageUpscaleModelActionConfig] = Field(default_factory=list, description="Actions this image upscale component exposes to workflows.")
