from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class AudioSilenceDetectorDriver(str, Enum):
    FFMPEG = "ffmpeg"

class CommonAudioSilenceDetectorComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.AUDIO_SILENCE_DETECTOR]
    driver: AudioSilenceDetectorDriver = Field(..., description="Backend implementation used to detect silence regions.")
