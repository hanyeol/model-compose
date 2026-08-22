from typing import Union, Literal, Optional
from enum import Enum
from pydantic import Field
from .common import CommonActionConfig
from .media import VideoAudioEncodingConfig

class AudioCaptureActionMethod(str, Enum):
    CAPTURE = "capture"

class AudioCaptureSource(str, Enum):
    SYSTEM     = "system"
    MICROPHONE = "microphone"

class AudioCaptureActionConfig(CommonActionConfig):
    method: Literal[AudioCaptureActionMethod.CAPTURE] = Field(default=AudioCaptureActionMethod.CAPTURE, description="Audio capture operation this action performs.")
    source: Union[AudioCaptureSource, str] = Field(default=AudioCaptureSource.MICROPHONE, description="Audio input source (system loopback or microphone).")
    device: Optional[Union[int, str]] = Field(default=None, description="Device index or name; when unset the platform default is used.")
    sample_rate: Optional[Union[int, str]] = Field(default=None, description="Sample rate in Hz applied to the captured audio.")
    channels: Optional[Union[int, str]] = Field(default=None, description="Channel count for the captured audio.")
    encoding: Optional[VideoAudioEncodingConfig] = Field(default=None, description="Encoding settings applied to the captured audio.")
    duration: Optional[Union[str, int, float]] = Field(default=None, description="Total capture duration; when unset, capture runs until stopped.")
