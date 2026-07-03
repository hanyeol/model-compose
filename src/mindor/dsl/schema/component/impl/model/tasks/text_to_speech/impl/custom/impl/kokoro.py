from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import KokoroTextToSpeechModelActionConfig
from ...common import CommonTextToSpeechModelComponentConfig
from .common import TextToSpeechModelFamily
from .....common import ModelDriver

class KokoroTextToSpeechModelComponentConfig(CommonTextToSpeechModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[TextToSpeechModelFamily.KOKORO]
    actions: List[KokoroTextToSpeechModelActionConfig] = Field(default_factory=list)
