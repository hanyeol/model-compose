from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class VideoAnalyzerDriverType(str, Enum):
    FFMPEG = "ffmpeg"

class CommonVideoAnalyzerComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.VIDEO_ANALYZER]
    driver: VideoAnalyzerDriverType = Field(..., description="Backend implementation used for video analysis.")
