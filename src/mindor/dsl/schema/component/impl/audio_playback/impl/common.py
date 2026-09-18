from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class AudioPlaybackDriverType(str, Enum):
    FFMPEG = "ffmpeg"

class CommonAudioPlaybackComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.AUDIO_PLAYBACK]
    driver: AudioPlaybackDriverType = Field(..., description="Backend implementation used for audio playback.")
