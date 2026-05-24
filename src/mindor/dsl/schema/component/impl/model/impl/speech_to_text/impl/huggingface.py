from typing import Literal, List
from enum import Enum
from pydantic import Field
from mindor.dsl.schema.action import SpeechToTextModelActionConfig
from .common import CommonSpeechToTextModelComponentConfig
from ...common import ModelDriver

class SpeechToTextModelArchitecture(str, Enum):
    WHISPER       = "whisper"
    WHISPER_LARGE = "whisper-large"

class HuggingfaceSpeechToTextModelComponentConfig(CommonSpeechToTextModelComponentConfig):
    driver: Literal[ModelDriver.HUGGINGFACE] = Field(default=ModelDriver.HUGGINGFACE)
    architecture: SpeechToTextModelArchitecture = Field(..., description="Model architecture.")
    actions: List[SpeechToTextModelActionConfig] = Field(default_factory=list)
