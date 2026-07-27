from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import LuxttsTextToSpeechModelActionConfig
from ...common import CommonTextToSpeechModelComponentConfig
from .common import TextToSpeechModelFamily
from .....common import ModelDriver

class LuxttsTextToSpeechModelComponentConfig(CommonTextToSpeechModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[TextToSpeechModelFamily.LUXTTS]
    actions: List[LuxttsTextToSpeechModelActionConfig] = Field(default_factory=list)
