from typing import Union, Optional, List
from pydantic import Field
from .common import CommonActionConfig
from .media import AudioEncoderConfig

class AudioConverterActionConfig(CommonActionConfig):
    audio: Union[str, List[str]] = Field(..., description="Audio source or list of sources to convert.")
    format: Optional[str] = Field(default=None, description="Output container format (e.g., wav, mp3, aac, flac, opus).")
    encoding: Optional[AudioEncoderConfig] = Field(default=None, description="Audio encoder settings such as codec, bitrate, sample rate, and channels.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input audios processed per batch.")
