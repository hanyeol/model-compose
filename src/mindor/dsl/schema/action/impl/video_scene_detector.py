from typing import Union, Optional, List
from enum import Enum
from pydantic import Field
from .common import CommonActionConfig

class VideoSceneDetectorType(str, Enum):
    CONTENT   = "content"
    ADAPTIVE  = "adaptive"
    THRESHOLD = "threshold"
    HISTOGRAM = "histogram"
    HASH      = "hash"

class VideoSceneDetectorActionConfig(CommonActionConfig):
    video: Union[str, List[str]] = Field(..., description="Video source(s).")
    detector: Optional[Union[VideoSceneDetectorType, str]] = Field(default=None, description="Scene detection algorithm. Interpretation depends on the driver.")
    threshold: Optional[Union[float, str]] = Field(default=None, description="Detection sensitivity threshold.")
    start_time: Optional[str] = Field(default=None, description="Start time for detection (e.g. '00:01:00', '60s').")
    end_time: Optional[str] = Field(default=None, description="End time for detection (e.g. '00:05:00', '300s').")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input videos to process in a single batch.")
    streaming: Union[bool, str] = Field(default=False, description="Whether the unit result should be streamed instead of returned as a single value.")
