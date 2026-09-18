from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class AudioConverterDriverType(str, Enum):
    FFMPEG = "ffmpeg"

class CommonAudioConverterComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.AUDIO_CONVERTER]
    driver: AudioConverterDriverType = Field(..., description="Backend implementation used for audio conversion.")
