from typing import Union, List, Optional
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class CommonMusicTranscriptionParamsConfig(BaseModel):
    onset_threshold: Optional[Union[float, str]] = Field(default=None, description="Confidence threshold for detecting a note onset, from 0.0 to 1.0; higher values keep only the most confident onsets.")
    frame_threshold: Optional[Union[float, str]] = Field(default=None, description="Confidence threshold for sustaining a note across frames, from 0.0 to 1.0.")

class CommonMusicTranscriptionModelActionConfig(CommonModelActionConfig):
    audio: Union[str, List[str]] = Field(..., description="Input audio path, URL, or list of audio inputs to transcribe.")
    batch_size: Union[int, str] = Field(default=1, description="Number of audio inputs processed per batch.")
    params: CommonMusicTranscriptionParamsConfig = Field(default_factory=CommonMusicTranscriptionParamsConfig, description="Detection thresholds applied to the transcriber.")
