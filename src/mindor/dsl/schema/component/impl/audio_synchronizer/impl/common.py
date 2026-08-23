from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class AudioSynchronizerDriver(str, Enum):
    FFMPEG = "ffmpeg"

class CommonAudioSynchronizerComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.AUDIO_SYNCHRONIZER]
    driver: AudioSynchronizerDriver = Field(..., description="Backend implementation used for audio synchronization.")
