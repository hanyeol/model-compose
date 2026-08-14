from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .common import CommonActionConfig

class VideoFrameExtractorActionConfig(CommonActionConfig):
    video: Union[str, List[str]] = Field(..., description="Video source or list of sources to extract frames from.")
    frame_interval: Union[int, str] = Field(default=1, description="Sampling stride; 1 keeps every frame, 2 keeps every second frame, and so on.")
    start_time: Optional[str] = Field(default=None, description="Time in the source at which extraction begins (e.g., 00:01:00, 60s).")
    end_time: Optional[str] = Field(default=None, description="Time in the source at which extraction stops (e.g., 00:05:00, 300s).")
    max_frame_count: Optional[Union[int, str]] = Field(default=None, description="Maximum number of frames to extract; unset means no limit.")
    filename_format: Optional[str] = Field(default=None, description="Per-frame filename pattern (e.g., frame-%04d.png); when set, each frame includes a filename key.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input videos processed per batch.")
    streaming: Union[bool, str] = Field(default=False, description="Whether frames are emitted incrementally as they are extracted.")
