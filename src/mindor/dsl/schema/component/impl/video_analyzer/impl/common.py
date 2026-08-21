from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class VideoAnalyzerDriver(str, Enum):
    FFMPEG = "ffmpeg"

class CommonVideoAnalyzerComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.VIDEO_ANALYZER]
    driver: VideoAnalyzerDriver = Field(..., description="Backend implementation used for video analysis.")
