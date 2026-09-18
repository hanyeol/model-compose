from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class VideoClipperDriverType(str, Enum):
    FFMPEG = "ffmpeg"

class CommonVideoClipperComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.VIDEO_CLIPPER]
    driver: VideoClipperDriverType = Field(..., description="Backend implementation used for video clipping.")
