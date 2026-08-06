from typing import Union, Optional, List
from pydantic import BaseModel, Field
from .common import CommonActionConfig

class AudioSpanConfig(BaseModel):
    start_time: Union[str, float, int] = Field(..., description="Clip start time (e.g. '00:00:10', '10s', 10.5).")
    end_time: Union[str, float, int] = Field(..., description="Clip end time (e.g. '00:00:20', '20s', 20.0).")

class AudioClipperActionConfig(CommonActionConfig):
    audio: Union[str, List[str]] = Field(..., description="Audio source(s).")
    span: Union[AudioSpanConfig, List[AudioSpanConfig], str] = Field(..., description="Time span(s) to clip. A single object yields one clip; a list yields one per span.")
    merge: Union[bool, str] = Field(default=False, description="If true, concatenate all clips into a single audio.")
    return_timestamp: Union[bool, str] = Field(default=False, description="If true, each clip carries its source span alongside the audio.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input sources per batch.")
