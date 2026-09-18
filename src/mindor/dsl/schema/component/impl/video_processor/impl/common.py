from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class VideoProcessorDriverType(str, Enum):
    FFMPEG = "ffmpeg"

class CommonVideoProcessorComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.VIDEO_PROCESSOR]
    driver: VideoProcessorDriverType = Field(..., description="Backend implementation used for video processing.")
