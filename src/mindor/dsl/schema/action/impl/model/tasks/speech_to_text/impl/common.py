from typing import Union, Literal, Optional, List
from pydantic import Field
from ...common import CommonModelActionConfig

class CommonSpeechToTextModelActionConfig(CommonModelActionConfig):
    audio: Union[str, List[str]] = Field(..., description="Audio to transcribe, or a list of audios.")
    language: Optional[str] = Field(default=None, description="Language code of the input audio (e.g., en, ko); unset triggers auto-detection.")
    return_timestamps: Union[bool, str] = Field(default=False, description="Whether per-segment timestamps are included in the output.")
    timestamp_level: Union[Literal[ "segment", "word" ], str] = Field(default="segment", description="Timestamp granularity applied when `return_timestamps` is enabled.")
    time_offset: Optional[Union[Union[str, float, int], List[Union[str, float, int]], str]] = Field(default=None, description="Offset added to each segment's start and end times; scalar values broadcast, lists pair per audio.")
    batch_size: Union[int, str] = Field(default=1, description="Number of audio inputs processed per batch.")
    streaming: Union[bool, str] = Field(default=False, description="Whether transcribed tokens are emitted incrementally as they are produced.")
