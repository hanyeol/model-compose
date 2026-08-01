from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import SpeechToTextModelActionConfig
from ...common import CommonSpeechToTextModelComponentConfig
from .common import SpeechToTextModelFamily
from .....common import ModelDriver

class FunAsrSpeechToTextModelComponentConfig(CommonSpeechToTextModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[SpeechToTextModelFamily.FUN_ASR]
    itn: bool = Field(default=True, description="Inverse text normalization (e.g. spoken numbers → digits).")
    actions: List[SpeechToTextModelActionConfig] = Field(default_factory=list)
