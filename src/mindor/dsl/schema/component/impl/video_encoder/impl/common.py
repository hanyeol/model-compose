from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class VideoEncoderDriverType(str, Enum):
    FFMPEG = "ffmpeg"

class CommonVideoEncoderComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.VIDEO_ENCODER]
    driver: VideoEncoderDriverType = Field(..., description="Backend implementation used for video encoding.")
