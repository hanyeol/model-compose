from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import SwinIRImageUpscaleModelActionConfig
from .common import CommonImageUpscaleModelComponentConfig, ImageUpscaleModelFamily

class SwinIRImageUpscaleModelComponentConfig(CommonImageUpscaleModelComponentConfig):
    family: Literal[ImageUpscaleModelFamily.SWINIR]
    actions: List[SwinIRImageUpscaleModelActionConfig] = Field(default_factory=list)
