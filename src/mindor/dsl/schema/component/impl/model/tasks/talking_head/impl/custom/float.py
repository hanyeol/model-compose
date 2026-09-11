from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import FloatTalkingHeadModelActionConfig
from ..common import CommonTalkingHeadModelComponentConfig
from .common import TalkingHeadModelFamily
from ....common import ModelDriver

class FloatTalkingHeadModelComponentConfig(CommonTalkingHeadModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[TalkingHeadModelFamily.FLOAT]
    actions: List[FloatTalkingHeadModelActionConfig] = Field(default_factory=list, description="Actions this talking-head component exposes to workflows.")
