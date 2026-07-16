from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class VideoEncoderDriver(str, Enum):
    FFMPEG = "ffmpeg"

class CommonVideoEncoderComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.VIDEO_ENCODER]
    driver: VideoEncoderDriver = Field(..., description="Video encoding backend driver.")
