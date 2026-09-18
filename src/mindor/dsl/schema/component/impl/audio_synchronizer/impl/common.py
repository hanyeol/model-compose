from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class AudioSynchronizerDriverType(str, Enum):
    NATIVE = "native"
    FFMPEG = "ffmpeg"

class CommonAudioSynchronizerComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.AUDIO_SYNCHRONIZER]
    driver: AudioSynchronizerDriverType = Field(..., description="Backend implementation used for audio synchronization.")
