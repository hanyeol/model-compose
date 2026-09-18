from typing import Union, Literal, List
from pydantic import Field
from mindor.dsl.schema.action import EsrganImageUpscaleModelActionConfig
from ..common import CommonImageUpscaleModelComponentConfig
from .common import ImageUpscaleModelFamily
from ....common import ModelDriverType

class EsrganImageUpscaleModelComponentConfig(CommonImageUpscaleModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[ImageUpscaleModelFamily.ESRGAN]
    scale: Union[int, str] = Field(default=2, description="Multiplier applied to output resolution.")
    actions: List[EsrganImageUpscaleModelActionConfig] = Field(default_factory=list, description="Actions this image upscale component exposes to workflows.")
