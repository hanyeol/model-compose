from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class MusicSegmentDetectorDriver(str, Enum):
    NATIVE = "native"

class CommonMusicSegmentDetectorComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.MUSIC_SEGMENT_DETECTOR]
    driver: MusicSegmentDetectorDriver = Field(..., description="Backend implementation used to detect audio segment boundaries.")
