from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import LdsrImageUpscaleModelActionConfig
from .common import CommonImageUpscaleModelComponentConfig, ImageUpscaleModelFamily

class LdsrImageUpscaleModelComponentConfig(CommonImageUpscaleModelComponentConfig):
    family: Literal[ImageUpscaleModelFamily.LDSR]
    actions: List[LdsrImageUpscaleModelActionConfig] = Field(default_factory=list)
