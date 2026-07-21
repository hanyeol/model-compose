from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import NativeSentenceSplitterActionConfig
from .common import CommonSentenceSplitterComponentConfig, SentenceSplitterDriver

class NativeSentenceSplitterComponentConfig(CommonSentenceSplitterComponentConfig):
    driver: Literal[SentenceSplitterDriver.NATIVE]
    actions: List[NativeSentenceSplitterActionConfig] = Field(default_factory=list)
