from typing import Union, Optional, List
from pydantic import BaseModel, Field
from .common import CommonActionConfig

class AudioSpanConfig(BaseModel):
    start_time: Union[str, float, int] = Field(..., description="Clip start time (e.g. '00:00:10', '10s', 10.5).")
    end_time: Union[str, float, int] = Field(..., description="Clip end time (e.g. '00:00:20', '20s', 20.0).")

class AudioClipperActionConfig(CommonActionConfig):
    audio: Union[str, List[str]] = Field(..., description="Audio source(s).")
    span: Union[AudioSpanConfig, List[AudioSpanConfig], str] = Field(..., description="One or more time spans to clip out of each audio source. A single span object yields a single clip; a list yields one clip per span.")
    merge: Union[bool, str] = Field(default=False, description="If true, concatenate all clips per source into a single audio; otherwise return a list of clips.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input sources per batch.")
