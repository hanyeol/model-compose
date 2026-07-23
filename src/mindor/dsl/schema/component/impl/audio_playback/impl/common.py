from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class AudioPlaybackDriver(str, Enum):
    FFMPEG = "ffmpeg"

class CommonAudioPlaybackComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.AUDIO_PLAYBACK]
    driver: AudioPlaybackDriver = Field(..., description="Audio playback backend driver.")
