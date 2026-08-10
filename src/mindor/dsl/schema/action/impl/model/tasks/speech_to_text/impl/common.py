from typing import Union, Literal, Optional, List
from pydantic import Field
from ...common import CommonModelActionConfig

class CommonSpeechToTextModelActionConfig(CommonModelActionConfig):
    audio: Union[str, List[str]] = Field(..., description="Input audio file path, URL, or list of audio inputs.")
    language: Optional[str] = Field(default=None, description="Language code (e.g. 'en', 'ko'). None for auto-detection.")
    return_timestamps: Union[bool, str] = Field(default=False, description="Whether to include per-segment timestamps in the output.")
    timestamp_level: Union[Literal[ "segment", "word" ], str] = Field(default="segment", description="Timestamp granularity when return_timestamps is enabled.")
    time_offset: Optional[Union[Union[str, float, int], List[Union[str, float, int]], str]] = Field(default=None, description="Offset added to each segment's start_time and end_time. Broadcast when scalar; paired per audio when list/stream.")
    batch_size: Union[int, str] = Field(default=1, description="Audio inputs per batch.")
    streaming: Union[bool, str] = Field(default=False, description="Whether to stream transcribed tokens as they are produced.")
