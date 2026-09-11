from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import SonicTalkingHeadModelActionConfig
from ..common import CommonTalkingHeadModelComponentConfig
from .common import TalkingHeadModelFamily
from ....common import ModelDriver

class SonicTalkingHeadModelComponentConfig(CommonTalkingHeadModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[TalkingHeadModelFamily.SONIC]
    actions: List[SonicTalkingHeadModelActionConfig] = Field(default_factory=list, description="Actions this talking-head component exposes to workflows.")
