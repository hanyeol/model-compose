from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import SwinIRImageUpscaleModelActionConfig
from ..common import CommonImageUpscaleModelComponentConfig
from .common import ImageUpscaleModelFamily
from ....common import ModelDriverType

class SwinIRImageUpscaleModelComponentConfig(CommonImageUpscaleModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[ImageUpscaleModelFamily.SWINIR]
    actions: List[SwinIRImageUpscaleModelActionConfig] = Field(default_factory=list, description="Actions this image upscale component exposes to workflows.")
