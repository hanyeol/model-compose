from typing import Union, Optional, List
from pydantic import BaseModel, Field
from .common import CommonActionConfig

class VideoSpanConfig(BaseModel):
    start_time: Union[str, float, int] = Field(..., description="Clip start time (e.g. '00:00:10', '10s', 10.5).")
    end_time: Union[str, float, int] = Field(..., description="Clip end time (e.g. '00:00:20', '20s', 20.0).")

class VideoClipperActionConfig(CommonActionConfig):
    video: Union[str, List[str]] = Field(..., description="Video source or list of sources to clip.")
    span: Union[VideoSpanConfig, List[VideoSpanConfig], str] = Field(..., description="Time span or spans to clip from each video. A single object yields one clip; a list yields one per span.")
    merge: Union[bool, str] = Field(default=False, description="Whether to concatenate all clips per source into a single video.")
    return_timestamp: Union[bool, str] = Field(default=False, description="Whether each clip carries its source span alongside the video.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input sources processed per batch.")
