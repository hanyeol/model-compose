from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import Hallo3TalkingHeadModelActionConfig
from ..common import CommonTalkingHeadModelComponentConfig
from .common import TalkingHeadModelFamily
from ....common import ModelDriverType

class Hallo3TalkingHeadModelComponentConfig(CommonTalkingHeadModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[TalkingHeadModelFamily.HALLO3]
    actions: List[Hallo3TalkingHeadModelActionConfig] = Field(default_factory=list, description="Actions this talking-head component exposes to workflows.")
