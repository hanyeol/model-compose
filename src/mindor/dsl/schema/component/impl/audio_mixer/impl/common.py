from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class AudioMixerDriver(str, Enum):
    FFMPEG = "ffmpeg"

class CommonAudioMixerComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.AUDIO_MIXER]
    driver: AudioMixerDriver = Field(..., description="Backend implementation used for audio mixing.")
