from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class VideoCaptureDriver(str, Enum):
    FFMPEG = "ffmpeg"

class CommonVideoCaptureComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.VIDEO_CAPTURE]
    driver: VideoCaptureDriver = Field(..., description="Backend implementation used to capture video.")
