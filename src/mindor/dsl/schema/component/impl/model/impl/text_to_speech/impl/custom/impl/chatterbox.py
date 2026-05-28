from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import ChatterboxTextToSpeechModelActionConfig
from ...common import CommonTextToSpeechModelComponentConfig
from .common import TextToSpeechModelFamily
from .....common import ModelDriver

class ChatterboxTextToSpeechModelComponentConfig(CommonTextToSpeechModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[TextToSpeechModelFamily.CHATTERBOX]
    actions: List[ChatterboxTextToSpeechModelActionConfig] = Field(default_factory=list)
