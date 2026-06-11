from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .common import CommonActionConfig

class VideoFrameExtractorActionConfig(CommonActionConfig):
    video: Any = Field(..., description="Video source.")
    frame_interval: Union[int, str] = Field(default=1, description="Frame interval. 1 = every frame, 2 = every 2nd frame, etc.")
    start_time: Optional[str] = Field(default=None, description="Start time for extraction (e.g. '00:01:00', '60s').")
    end_time: Optional[str] = Field(default=None, description="End time for extraction (e.g. '00:05:00', '300s').")
    max_frame_count: Optional[Union[int, str]] = Field(default=None, description="Maximum number of frames to extract. None = no limit.")
