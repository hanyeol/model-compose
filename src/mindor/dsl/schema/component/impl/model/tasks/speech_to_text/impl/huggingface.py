from typing import Literal, List
from enum import Enum
from pydantic import Field
from mindor.dsl.schema.action import SpeechToTextModelActionConfig
from .common import CommonSpeechToTextModelComponentConfig
from ...common import ModelDriver

class HuggingfaceSpeechToTextModelArchitecture(str, Enum):
    AUTO    = "auto"
    WHISPER = "whisper"

class HuggingfaceSpeechToTextModelComponentConfig(CommonSpeechToTextModelComponentConfig):
    driver: Literal[ModelDriver.HUGGINGFACE] = Field(default=ModelDriver.HUGGINGFACE)
    architecture: HuggingfaceSpeechToTextModelArchitecture = Field(default=HuggingfaceSpeechToTextModelArchitecture.AUTO, description="Model architecture.")
    actions: List[SpeechToTextModelActionConfig] = Field(default_factory=list)
