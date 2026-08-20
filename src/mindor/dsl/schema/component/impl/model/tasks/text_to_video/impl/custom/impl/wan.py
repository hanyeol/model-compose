from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import TextToVideoModelActionConfig
from ...common import CommonTextToVideoModelComponentConfig
from .common import TextToVideoModelFamily, WanTextToVideoPreset
from .....common import ModelDriver

class WanTextToVideoModelComponentConfig(CommonTextToVideoModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[TextToVideoModelFamily.WAN]
    preset: WanTextToVideoPreset = Field(default=WanTextToVideoPreset.WAN22_TI2V_5B, description="Wan model preset selecting the checkpoint variant.")
    actions: List[TextToVideoModelActionConfig] = Field(default_factory=list, description="Actions this text-to-video component exposes to workflows.")
