from typing import Literal, List
from enum import Enum
from pydantic import Field
from mindor.dsl.schema.action import TextToVideoModelActionConfig
from ..common import CommonTextToVideoModelComponentConfig
from .common import TextToVideoModelFamily
from ....common import ModelDriverType

class WanTextToVideoPreset(str, Enum):
    T2V_A14B = "t2v-a14b"
    TI2V_5B  = "ti2v-5b"

class WanTextToVideoModelComponentConfig(CommonTextToVideoModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[TextToVideoModelFamily.WAN]
    preset: WanTextToVideoPreset = Field(default=WanTextToVideoPreset.T2V_A14B, description="Wan model preset selecting the checkpoint variant.")
    cpu_offload: bool = Field(default=False, description="Offload submodules to CPU during generation to save VRAM.")
    actions: List[TextToVideoModelActionConfig] = Field(default_factory=list, description="Actions this text-to-video component exposes to workflows.")
