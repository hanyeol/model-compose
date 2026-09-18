from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class SentenceSplitterDriverType(str, Enum):
    NATIVE = "native"

class CommonSentenceSplitterComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.SENTENCE_SPLITTER]
    driver: SentenceSplitterDriverType = Field(..., description="Backend implementation used to split text into sentences.")
