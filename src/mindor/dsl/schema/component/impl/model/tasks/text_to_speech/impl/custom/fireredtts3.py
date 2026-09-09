from typing import Literal, List
from enum import Enum
from pydantic import Field
from mindor.dsl.schema.action import FireRedTextToSpeechModelActionConfig
from ..common import CommonTextToSpeechModelComponentConfig
from .common import TextToSpeechModelFamily
from ....common import ModelDriver

class FireRedTextToSpeechPreset(str, Enum):
    BASE     = "base"
    INSTRUCT = "instruct"

class FireRedTextToSpeechModelComponentConfig(CommonTextToSpeechModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[TextToSpeechModelFamily.FIREREDTTS3]
    preset: FireRedTextToSpeechPreset = Field(default=FireRedTextToSpeechPreset.BASE, description="FireRedTTS3 model preset selecting the Base or Instruct checkpoint.")
    actions: List[FireRedTextToSpeechModelActionConfig] = Field(default_factory=list, description="Actions this text-to-speech component exposes to workflows.")
