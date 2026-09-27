from typing import Literal, List
from enum import Enum
from pydantic import Field
from mindor.dsl.schema.action import ImageToVideoModelActionConfig
from ..common import CommonImageToVideoModelComponentConfig
from .common import ImageToVideoModelFamily
from ....common import ModelDriverType

class WanImageToVideoPreset(str, Enum):
    I2V_A14B = "i2v-a14b"
    TI2V_5B  = "ti2v-5b"

class WanImageToVideoModelComponentConfig(CommonImageToVideoModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[ImageToVideoModelFamily.WAN]
    preset: WanImageToVideoPreset = Field(default=WanImageToVideoPreset.I2V_A14B, description="Wan model preset selecting the checkpoint variant.")
    cpu_offload: bool = Field(default=False, description="Offload submodules to CPU during generation to save VRAM.")
    actions: List[ImageToVideoModelActionConfig] = Field(default_factory=list, description="Actions this image-to-video component exposes to workflows.")
