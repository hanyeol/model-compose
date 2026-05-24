from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import TextToSpeechModelActionConfig
from ..common import CommonTextToSpeechModelComponentConfig
from .custom import CustomTextToSpeechModelFamily
from ....common import ModelDriver

class QwenTextToSpeechModelComponentConfig(CommonTextToSpeechModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[CustomTextToSpeechModelFamily.QWEN]
    actions: List[TextToSpeechModelActionConfig] = Field(default_factory=list)
