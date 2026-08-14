from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class AudioClipperDriver(str, Enum):
    FFMPEG = "ffmpeg"

class CommonAudioClipperComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.AUDIO_CLIPPER]
    driver: AudioClipperDriver = Field(..., description="Backend implementation used for audio clipping.")
