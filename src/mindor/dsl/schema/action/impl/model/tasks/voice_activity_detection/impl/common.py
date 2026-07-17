from typing import Union, Optional, List
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class VoiceActivityDetectionParamsConfig(BaseModel):
    threshold: Union[float, str] = Field(default=0.5, description="Speech probability threshold above which a frame is treated as speech.")
    min_speech_duration: Union[str, float, int] = Field(default="250ms", description="Minimum speech chunk duration (e.g. '250ms', '0.25s'); shorter chunks are discarded.")
    max_speech_duration: Optional[Union[str, float, int]] = Field(default=None, description="Maximum speech chunk duration (e.g. '30s'); longer chunks are forcibly split. None means unlimited.")
    min_silence_duration: Union[str, float, int] = Field(default="500ms", description="Minimum silence duration (e.g. '500ms', '0.5s') required to split adjacent speech chunks.")
    speech_padding_time: Union[str, float, int] = Field(default="100ms", description="Padding time (e.g. '100ms', '0.1s') added to both sides of each detected speech chunk.")

class VoiceActivityDetectionModelActionConfig(CommonModelActionConfig):
    audio: Union[Union[str, List[str]], str] = Field(..., description="Input audio file path, URL, or list of audio inputs.")
    sample_rate: Union[int, str] = Field(default=16000, description="Sample rate of the input audio in Hz (16000 or 8000).")
    batch_size: Union[int, str] = Field(default=1, description="Audio inputs per batch.")
    streaming: Union[bool, str] = Field(default=False, description="Whether to stream detected speech segments as they are confirmed.")
    params: VoiceActivityDetectionParamsConfig = Field(default_factory=VoiceActivityDetectionParamsConfig, description="Voice activity detection parameters.")
