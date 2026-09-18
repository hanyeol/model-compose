from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class AudioAnalyzerDriverType(str, Enum):
    FFMPEG = "ffmpeg"

class CommonAudioAnalyzerComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.AUDIO_ANALYZER]
    driver: AudioAnalyzerDriverType = Field(..., description="Backend implementation used for audio analysis.")
