from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import TalkingHeadModelActionConfig
from ..common import CommonTalkingHeadModelComponentConfig
from .common import TalkingHeadModelFamily, SadTalkerPreset
from ....common import ModelDriver

class SadTalkerTalkingHeadModelComponentConfig(CommonTalkingHeadModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[TalkingHeadModelFamily.SADTALKER]
    preset: SadTalkerPreset = Field(default=SadTalkerPreset.V002_256, description="SadTalker checkpoint variant to load.")
    actions: List[TalkingHeadModelActionConfig] = Field(default_factory=list, description="Actions this talking-head component exposes to workflows.")
