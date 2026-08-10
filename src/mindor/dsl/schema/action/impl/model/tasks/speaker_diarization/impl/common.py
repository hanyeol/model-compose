from typing import Union, Optional, List
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class SpeakerDiarizationParamsConfig(BaseModel):
    min_segment_duration: Union[str, float, int] = Field(default="0s", description="Minimum segment duration (e.g. '250ms', '0.25s'); shorter turns are discarded.")
    merge_gap: Union[str, float, int] = Field(default="0s", description="Adjacent segments from the same speaker separated by <= this gap (e.g. '500ms') are merged.")

class SpeakerDiarizationModelActionConfig(CommonModelActionConfig):
    audio: Union[str, List[str]] = Field(..., description="Input audio file path, URL, or list of audio inputs.")
    num_speakers: Optional[Union[int, str]] = Field(default=None, description="Exact number of speakers if known; otherwise leave empty and use min/max hints.")
    min_speakers: Optional[Union[int, str]] = Field(default=None, description="Minimum number of speakers to consider.")
    max_speakers: Optional[Union[int, str]] = Field(default=None, description="Maximum number of speakers to consider.")
    batch_size: Union[int, str] = Field(default=1, description="Audio inputs per batch.")
    streaming: Union[bool, str] = Field(default=False, description="Whether to stream speaker turns as they are confirmed.")
    params: SpeakerDiarizationParamsConfig = Field(default_factory=SpeakerDiarizationParamsConfig, description="Speaker diarization parameters.")
