from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import NativeSentenceSplitterActionConfig
from .common import CommonSentenceSplitterComponentConfig, SentenceSplitterDriverType

class NativeSentenceSplitterComponentConfig(CommonSentenceSplitterComponentConfig):
    driver: Literal[SentenceSplitterDriverType.NATIVE]
    actions: List[NativeSentenceSplitterActionConfig] = Field(default_factory=list)
