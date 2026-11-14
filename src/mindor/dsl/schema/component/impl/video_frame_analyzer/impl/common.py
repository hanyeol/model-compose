from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class VideoFrameAnalyzerDriverType(str, Enum):
    NATIVE = "native"
    OPENCV = "opencv"

class CommonVideoFrameAnalyzerComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.VIDEO_FRAME_ANALYZER]
    driver: VideoFrameAnalyzerDriverType = Field(..., description="Backend implementation used for video frame analysis.")
