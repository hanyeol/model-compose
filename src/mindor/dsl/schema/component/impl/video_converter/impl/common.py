from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class VideoConverterDriverType(str, Enum):
    FFMPEG = "ffmpeg"

class CommonVideoConverterComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.VIDEO_CONVERTER]
    driver: VideoConverterDriverType = Field(..., description="Backend implementation used for video conversion.")
