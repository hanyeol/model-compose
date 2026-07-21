from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class SentenceSplitterDriver(str, Enum):
    NATIVE = "native"

class CommonSentenceSplitterComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.SENTENCE_SPLITTER]
    driver: SentenceSplitterDriver = Field(..., description="Sentence splitter backend driver.")
