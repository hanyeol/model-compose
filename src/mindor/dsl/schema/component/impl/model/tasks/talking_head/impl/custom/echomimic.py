from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import EchoMimicTalkingHeadModelActionConfig
from ..common import CommonTalkingHeadModelComponentConfig
from .common import TalkingHeadModelFamily, EchoMimicPreset
from ....common import ModelDriver

class EchoMimicTalkingHeadModelComponentConfig(CommonTalkingHeadModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[TalkingHeadModelFamily.ECHOMIMIC]
    preset: EchoMimicPreset = Field(default=EchoMimicPreset.V1, description="EchoMimic release: v1 (portrait) or v2 (half-body).")
    actions: List[EchoMimicTalkingHeadModelActionConfig] = Field(default_factory=list, description="Actions this talking-head component exposes to workflows.")
