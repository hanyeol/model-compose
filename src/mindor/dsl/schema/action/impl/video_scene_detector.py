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
    video: Union[str, List[str]] = Field(..., description="Video source or list of sources to analyze for scene changes.")
    detector: Optional[Union[VideoSceneDetectorType, str]] = Field(default=None, description="Scene detection algorithm; interpretation depends on the driver.")
    threshold: Optional[Union[float, str]] = Field(default=None, description="Detection sensitivity threshold used by the chosen algorithm.")
    start_time: Optional[str] = Field(default=None, description="Time in the source at which detection begins (e.g., 00:01:00, 60s).")
    end_time: Optional[str] = Field(default=None, description="Time in the source at which detection stops (e.g., 00:05:00, 300s).")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input videos processed per batch.")
    streaming: Union[bool, str] = Field(default=False, description="Whether scene results are emitted incrementally as they are detected.")
