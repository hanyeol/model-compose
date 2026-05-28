from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import SpeechToTextModelActionConfig
from ..common import CommonSpeechToTextModelComponentConfig
from .impl.common import SpeechToTextModelFamily
from ....common import ModelDriver

class CustomSpeechToTextModelComponentConfig(CommonSpeechToTextModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: SpeechToTextModelFamily = Field(..., description="Model family.")
    actions: List[SpeechToTextModelActionConfig] = Field(default_factory=list)
