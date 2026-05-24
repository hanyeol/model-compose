from typing import Literal, List
from enum import Enum
from pydantic import Field
from mindor.dsl.schema.action import SpeechToTextModelActionConfig
from ..common import CommonSpeechToTextModelComponentConfig
from ....common import ModelDriver

class CustomSpeechToTextModelFamily(str, Enum):
    pass

class CustomSpeechToTextModelComponentConfig(CommonSpeechToTextModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: CustomSpeechToTextModelFamily = Field(..., description="Model family.")
    actions: List[SpeechToTextModelActionConfig] = Field(default_factory=list)
