from typing import Union, Optional, List
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class SpeechSeparationParamsConfig(BaseModel):
    num_speakers: Union[int, str] = Field(default=2, description="Number of speakers to separate (2 or 3). Determines which pretrained checkpoint is used when the component 'model' is not explicitly set.")

class SpeechSeparationModelActionConfig(CommonModelActionConfig):
    audio: Union[Union[str, List[str]], str] = Field(..., description="Input audio file path, URL, or list of audio inputs.")
    sample_rate: Union[int, str] = Field(default=8000, description="Sample rate of the input audio in Hz. SepFormer WSJ mixes are trained at 8000 Hz.")
    batch_size: Union[int, str] = Field(default=1, description="Audio inputs per batch.")
    streaming: Union[bool, str] = Field(default=False, description="Whether to stream separated tracks as they are produced.")
    params: SpeechSeparationParamsConfig = Field(default_factory=SpeechSeparationParamsConfig, description="Speech separation parameters.")
