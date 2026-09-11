from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import TalkingHeadModelActionConfig
from ..common import CommonTalkingHeadModelComponentConfig
from .common import TalkingHeadModelFamily, SadTalkerPreset, SadTalkerPreprocess
from ....common import ModelDriver

class SadTalkerTalkingHeadModelComponentConfig(CommonTalkingHeadModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[TalkingHeadModelFamily.SADTALKER]
    preset: SadTalkerPreset = Field(default=SadTalkerPreset.V002_256, description="SadTalker checkpoint variant to load.")
    preprocess: SadTalkerPreprocess = Field(default=SadTalkerPreprocess.CROP, description="Face preprocessing mode; determines which mapping checkpoint is loaded and cannot vary per action.")
    actions: List[TalkingHeadModelActionConfig] = Field(default_factory=list, description="Actions this talking-head component exposes to workflows.")
