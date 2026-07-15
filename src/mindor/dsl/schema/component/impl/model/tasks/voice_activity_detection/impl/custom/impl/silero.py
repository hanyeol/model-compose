from typing import Literal, List, Optional, Union
from pydantic import Field
from mindor.dsl.schema.action import VoiceActivityDetectionModelActionConfig
from ...common import CommonVoiceActivityDetectionModelComponentConfig
from .common import VoiceActivityDetectionModelFamily
from .....common import ModelDriver, ModelConfig

class SileroVoiceActivityDetectionModelComponentConfig(CommonVoiceActivityDetectionModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[VoiceActivityDetectionModelFamily.SILERO]
    model: Optional[Union[str, ModelConfig]] = Field(default=None, description="Ignored for Silero; the model ships inside the silero-vad pip package.")
    actions: List[VoiceActivityDetectionModelActionConfig] = Field(default_factory=list)
