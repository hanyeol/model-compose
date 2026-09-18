from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class AudioSilenceDetectorDriverType(str, Enum):
    FFMPEG = "ffmpeg"

class CommonAudioSilenceDetectorComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.AUDIO_SILENCE_DETECTOR]
    driver: AudioSilenceDetectorDriverType = Field(..., description="Backend implementation used to detect silence regions.")
