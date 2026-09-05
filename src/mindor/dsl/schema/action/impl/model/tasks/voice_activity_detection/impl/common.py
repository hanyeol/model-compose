from typing import Union, Optional, List
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class VoiceActivityDetectionParamsConfig(BaseModel):
    threshold: Union[float, str] = Field(default=0.5, description="Speech probability above which a frame is treated as speech.")
    min_speech_duration: Union[str, float, int] = Field(default="250ms", description="Minimum speech chunk duration (e.g., 250ms, 0.25s); shorter chunks are discarded.")
    max_speech_duration: Optional[Union[str, float, int]] = Field(default=None, description="Maximum speech chunk duration (e.g., 30s); longer chunks are forcibly split. Unset means unlimited.")
    min_silence_duration: Union[str, float, int] = Field(default="500ms", description="Minimum silence duration required to split adjacent speech chunks (e.g., 500ms, 0.5s).")
    speech_padding_time: Union[str, float, int] = Field(default="100ms", description="Padding added to both sides of each detected speech chunk (e.g., 100ms, 0.1s).")

class VoiceActivityDetectionModelActionConfig(CommonModelActionConfig):
    audio: Union[str, List[str]] = Field(..., description="Audio to analyze, or a list of audios.")
    sample_rate: Union[int, str] = Field(default=16000, description="Sample rate of the input audio in Hz; typically 16000 or 8000.")
    batch_size: Union[int, str] = Field(default=1, description="Number of audio inputs processed per batch.")
    streaming: Union[bool, str] = Field(default=False, description="Whether detected speech segments are emitted incrementally as they are confirmed.")
    params: VoiceActivityDetectionParamsConfig = Field(default_factory=VoiceActivityDetectionParamsConfig, description="Threshold and duration parameters controlling voice activity detection.")
