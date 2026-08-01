from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import FunAsrSpeechToTextModelActionConfig
from ...common import CommonSpeechToTextModelComponentConfig
from .common import SpeechToTextModelFamily
from .....common import ModelDriver

class FunAsrSpeechToTextModelComponentConfig(CommonSpeechToTextModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[SpeechToTextModelFamily.FUN_ASR]
    inverse_text_normalization: bool = Field(default=True, description="Convert spoken forms to written forms (e.g. 'twenty five' → '25').")
    actions: List[FunAsrSpeechToTextModelActionConfig] = Field(default_factory=list)
