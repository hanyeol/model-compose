from typing import Union, Optional, List
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class SpeakerDiarizationParamsConfig(BaseModel):
    min_segment_duration: Union[str, float, int] = Field(default="0s", description="Minimum segment duration (e.g., 250ms, 0.25s); shorter turns are discarded.")
    merge_gap: Union[str, float, int] = Field(default="0s", description="Adjacent same-speaker segments separated by no more than this gap are merged (e.g., 500ms).")

class SpeakerDiarizationModelActionConfig(CommonModelActionConfig):
    audio: Union[str, List[str]] = Field(..., description="Input audio path, URL, or list of audio inputs to diarize.")
    num_speakers: Optional[Union[int, str]] = Field(default=None, description="Exact number of speakers when known; otherwise leave unset and use the min/max hints.")
    min_speakers: Optional[Union[int, str]] = Field(default=None, description="Minimum number of speakers considered.")
    max_speakers: Optional[Union[int, str]] = Field(default=None, description="Maximum number of speakers considered.")
    batch_size: Union[int, str] = Field(default=1, description="Number of audio inputs processed per batch.")
    streaming: Union[bool, str] = Field(default=False, description="Whether speaker turns are emitted incrementally as they are confirmed.")
    params: SpeakerDiarizationParamsConfig = Field(default_factory=SpeakerDiarizationParamsConfig, description="Segment-shaping parameters applied to diarization output.")
