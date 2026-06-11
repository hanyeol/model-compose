from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import VideoFrameExtractorActionConfig
from .common import CommonComponentConfig, ComponentType

class VideoFrameExtractorDriver(str, Enum):
    OPENCV = "opencv"
    FFMPEG = "ffmpeg"

class VideoFrameExtractorComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.VIDEO_FRAME_EXTRACTOR]
    driver: Union[VideoFrameExtractorDriver, str] = Field(default=VideoFrameExtractorDriver.OPENCV, description="Video frame extraction backend driver.")
    actions: List[VideoFrameExtractorActionConfig] = Field(default_factory=list)
