from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import FasterWhisperSpeechToTextModelActionConfig
from ...common import CommonSpeechToTextModelComponentConfig
from .common import SpeechToTextModelFamily
from .....common import ModelDriver

class FasterWhisperSpeechToTextModelComponentConfig(CommonSpeechToTextModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[SpeechToTextModelFamily.FASTER_WHISPER]
    compute_type: str = Field(default="default", description="Compute type for inference (e.g. 'float16', 'int8', 'int8_float16', 'default').")
    actions: List[FasterWhisperSpeechToTextModelActionConfig] = Field(default_factory=list)
