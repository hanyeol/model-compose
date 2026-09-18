from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import NativeTranscriptCorrectorActionConfig
from .common import CommonTranscriptCorrectorComponentConfig, TranscriptCorrectorDriverType

class NativeTranscriptCorrectorComponentConfig(CommonTranscriptCorrectorComponentConfig):
    driver: Literal[TranscriptCorrectorDriverType.NATIVE]
    actions: List[NativeTranscriptCorrectorActionConfig] = Field(default_factory=list)
