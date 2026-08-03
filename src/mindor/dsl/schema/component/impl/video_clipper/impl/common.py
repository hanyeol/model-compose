from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class VideoClipperDriver(str, Enum):
    FFMPEG = "ffmpeg"

class CommonVideoClipperComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.VIDEO_CLIPPER]
    driver: VideoClipperDriver = Field(..., description="Video clipping backend driver.")
