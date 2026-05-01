from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field, model_validator
from .common import CommonActionConfig

class AudioSourceConfig(BaseModel):
    path: Optional[str] = Field(default=None, description="Audio file path or variable reference. Use when the source is a file.")
    data: Optional[Any] = Field(default=None, description="Raw audio data as bytes, stream, or variable reference. Use when the source is not a file (e.g. raw PCM stream).")
    format: Optional[str] = Field(default=None, description="Input format hint for raw or headerless audio (e.g. 's16le', 'f32le', 'mulaw'). Required when ffmpeg cannot auto-detect the format.")
    sample_rate: Optional[Union[int, str]] = Field(default=None, description="Input sample rate in Hz, required for raw audio (e.g. 22050, 44100).")
    channels: Optional[Union[int, str]] = Field(default=None, description="Input number of channels, required for raw audio (e.g. 1 for mono, 2 for stereo).")

    @model_validator(mode="after")
    def validate_source(self):
        if not self.path and not self.data:
            raise ValueError("Either 'path' or 'data' must be specified in AudioSourceConfig.")
        return self

class AudioConverterActionConfig(CommonActionConfig):
    source: Union[str, AudioSourceConfig] = Field(..., description="Audio file path, or AudioSourceConfig with format hints for raw or headerless audio.")
    format: Optional[str] = Field(default=None, description="Output format (e.g. 'wav', 'mp3', 'aac', 'flac', 'opus').")
    codec: Optional[str] = Field(default=None, description="Output audio codec (e.g. 'libmp3lame', 'aac', 'libopus', 'flac').")
    bitrate: Optional[str] = Field(default=None, description="Output audio bitrate for lossy formats (e.g. '128k', '192k', '320k').")
    sample_rate: Optional[Union[int, str]] = Field(default=None, description="Output sample rate in Hz (e.g. 44100).")
    channels: Optional[Union[int, str]] = Field(default=None, description="Output number of channels (e.g. 1 for mono, 2 for stereo).")
