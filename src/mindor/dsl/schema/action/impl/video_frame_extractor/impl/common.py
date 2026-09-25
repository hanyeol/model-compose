from typing import Union, Optional, List
from pydantic import Field
from ...common import CommonActionConfig

class CommonVideoFrameExtractorActionConfig(CommonActionConfig):
    video: Union[str, List[str]] = Field(..., description="Video source or list of sources to extract frames from.")
    frame_interval: Union[int, str] = Field(default=1, description="Sampling stride applied to frames.")
    start_time: Optional[str] = Field(default=None, description="Time in the source at which extraction begins (e.g., 00:01:00, 60s).")
    end_time: Optional[str] = Field(default=None, description="Time in the source at which extraction stops (e.g., 00:05:00, 300s).")
    max_frame_count: Optional[Union[int, str]] = Field(default=None, description="Maximum number of frames to extract.")
    filename_format: Optional[str] = Field(default=None, description="Per-frame filename pattern (e.g., frame-%04d.png).")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input videos processed per batch.")
    streaming: Union[bool, str] = Field(default=False, description="Whether frames are emitted incrementally as they are produced.")
