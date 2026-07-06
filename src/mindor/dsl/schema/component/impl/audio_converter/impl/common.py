from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class AudioConverterDriver(str, Enum):
    FFMPEG = "ffmpeg"

class CommonAudioConverterComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.AUDIO_CONVERTER]
    driver: AudioConverterDriver = Field(..., description="Audio conversion backend driver.")
