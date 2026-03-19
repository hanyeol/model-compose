from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from .common import CommonActionConfig

class VideoSceneDetectorType(str, Enum):
    CONTENT   = "content"
    ADAPTIVE  = "adaptive"
    THRESHOLD = "threshold"
    HISTOGRAM = "histogram"
    HASH      = "hash"

class VideoSceneDetectorActionConfig(CommonActionConfig):
    video: str = Field(..., description="Video file path or variable reference.")
    detector: Optional[Union[VideoSceneDetectorType, str]] = Field(default=None, description="Scene detection algorithm. Interpretation depends on the driver.")
    threshold: Optional[Union[float, str]] = Field(default=None, description="Detection sensitivity threshold.")
    start_time: Optional[str] = Field(default=None, description="Start time for detection (e.g. '00:01:00', '60s').")
    end_time: Optional[str] = Field(default=None, description="End time for detection (e.g. '00:05:00', '300s').")
