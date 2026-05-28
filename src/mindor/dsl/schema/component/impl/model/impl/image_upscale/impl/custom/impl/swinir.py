from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import SwinIRImageUpscaleModelActionConfig
from ...common import CommonImageUpscaleModelComponentConfig
from .common import ImageUpscaleModelFamily
from .....common import ModelDriver

class SwinIRImageUpscaleModelComponentConfig(CommonImageUpscaleModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[ImageUpscaleModelFamily.SWINIR]
    actions: List[SwinIRImageUpscaleModelActionConfig] = Field(default_factory=list)
