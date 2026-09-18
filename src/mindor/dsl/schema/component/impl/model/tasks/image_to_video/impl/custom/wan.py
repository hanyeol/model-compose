from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import ImageToVideoModelActionConfig
from ..common import CommonImageToVideoModelComponentConfig
from .common import ImageToVideoModelFamily, WanImageToVideoPreset
from ....common import ModelDriverType

class WanImageToVideoModelComponentConfig(CommonImageToVideoModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[ImageToVideoModelFamily.WAN]
    preset: WanImageToVideoPreset = Field(default=WanImageToVideoPreset.I2V_A14B, description="Wan model preset selecting the checkpoint variant.")
    actions: List[ImageToVideoModelActionConfig] = Field(default_factory=list, description="Actions this image-to-video component exposes to workflows.")
