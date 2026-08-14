from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class VideoFrameExtractorDriver(str, Enum):
    FFMPEG = "ffmpeg"
    OPENCV = "opencv"

class CommonVideoFrameExtractorComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.VIDEO_FRAME_EXTRACTOR]
    driver: VideoFrameExtractorDriver = Field(..., description="Backend implementation used to extract video frames.")
