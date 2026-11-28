from typing import Union, List, Optional
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class AudioSourceSeparationSpan(BaseModel):
    start: Union[float, str] = Field(..., description="Start time of the span in seconds.")
    end: Union[float, str] = Field(..., description="End time of the span in seconds.")

class CommonAudioSourceSeparationParamsConfig(BaseModel):
    sample_rate: Optional[Union[int, str]] = Field(default=None, description="Sample rate in Hz of the returned audio; defaults to the model's native rate.")

class CommonAudioSourceSeparationModelActionConfig(CommonModelActionConfig):
    audio: Union[str, List[str]] = Field(..., description="Audio to separate, or a list of audios.")
    prompt: Optional[Union[str, List[str]]] = Field(default=None, description="Natural-language description of the target sound; use lowercase noun-/verb-phrase form (e.g. 'thunder', 'man speaking').")
    spans: Optional[Union[List[AudioSourceSeparationSpan], str]] = Field(default=None, description="Optional time spans where the target sound occurs; each entry is `{start, end}` in seconds.")
    batch_size: Union[int, str] = Field(default=1, description="Number of audio inputs processed per batch.")
    params: CommonAudioSourceSeparationParamsConfig = Field(default_factory=CommonAudioSourceSeparationParamsConfig, description="Separation quality parameters.")
