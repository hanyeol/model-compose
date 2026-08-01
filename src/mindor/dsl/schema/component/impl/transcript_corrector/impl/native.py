from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import NativeTranscriptCorrectorActionConfig
from .common import CommonTranscriptCorrectorComponentConfig, TranscriptCorrectorDriver

class NativeTranscriptCorrectorComponentConfig(CommonTranscriptCorrectorComponentConfig):
    driver: Literal[TranscriptCorrectorDriver.NATIVE]
    actions: List[NativeTranscriptCorrectorActionConfig] = Field(default_factory=list)
