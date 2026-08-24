from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class AudioSegmentDetectorDriver(str, Enum):
    NATIVE = "native"

class CommonAudioSegmentDetectorComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.AUDIO_SEGMENT_DETECTOR]
    driver: AudioSegmentDetectorDriver = Field(..., description="Backend implementation used to detect audio segment boundaries.")
