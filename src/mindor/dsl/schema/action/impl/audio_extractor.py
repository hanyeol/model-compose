from typing import Union, Optional, List
from pydantic import Field
from .common import CommonActionConfig
from .media import AudioEncoderConfig

class AudioExtractorActionConfig(CommonActionConfig):
    source: Union[str, List[str]] = Field(..., description="Media source or list of sources (video or audio) to extract audio from.")
    format: Optional[str] = Field(default=None, description="Output audio format (e.g., mp3, wav, flac, aac, opus).")
    encoding: Optional[AudioEncoderConfig] = Field(default=None, description="Audio encoder settings such as codec, bitrate, sample rate, and channels.")
    track: Optional[Union[str, int]] = Field(default=None, description="Audio track index to extract from multi-track sources.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input sources processed per batch.")
