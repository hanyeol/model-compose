from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import SwinIRImageUpscaleModelActionConfig
from ..common import CommonImageUpscaleModelComponentConfig
from .custom import CustomImageUpscaleModelFamily
from ....common import ModelDriver

class SwinIRImageUpscaleModelComponentConfig(CommonImageUpscaleModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[CustomImageUpscaleModelFamily.SWINIR]
    actions: List[SwinIRImageUpscaleModelActionConfig] = Field(default_factory=list)
