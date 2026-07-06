from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class AudioExtractorDriver(str, Enum):
    FFMPEG = "ffmpeg"

class CommonAudioExtractorComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.AUDIO_EXTRACTOR]
    driver: AudioExtractorDriver = Field(..., description="Audio extraction backend driver.")
