from typing import Union, Optional, Any
from pydantic import Field
from .common import CommonActionConfig

class AudioConverterActionConfig(CommonActionConfig):
    audio: Any = Field(..., description="Audio source: file path, variable reference, or stream resource.")
    format: Optional[str] = Field(default=None, description="Output format (e.g. 'wav', 'mp3', 'aac', 'flac', 'opus').")
    codec: Optional[str] = Field(default=None, description="Output audio codec (e.g. 'libmp3lame', 'aac', 'libopus', 'flac').")
    bitrate: Optional[str] = Field(default=None, description="Output audio bitrate for lossy formats (e.g. '128k', '192k', '320k').")
    sample_rate: Optional[Union[int, str]] = Field(default=None, description="Output sample rate in Hz (e.g. 44100).")
    channels: Optional[Union[int, str]] = Field(default=None, description="Output number of channels (e.g. 1 for mono, 2 for stereo).")
