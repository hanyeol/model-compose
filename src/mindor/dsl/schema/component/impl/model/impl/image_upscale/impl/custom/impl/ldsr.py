from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import LdsrImageUpscaleModelActionConfig
from ...common import CommonImageUpscaleModelComponentConfig
from .common import ImageUpscaleModelFamily
from .....common import ModelDriver

class LdsrImageUpscaleModelComponentConfig(CommonImageUpscaleModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[ImageUpscaleModelFamily.LDSR]
    actions: List[LdsrImageUpscaleModelActionConfig] = Field(default_factory=list)
