from typing import Union, Optional, List
from pydantic import Field
from .common import CommonActionConfig

class AudioExtractorActionConfig(CommonActionConfig):
    source: Union[str, List[str]] = Field(..., description="Media source(s) (video or audio).")
    format: Optional[str] = Field(default=None, description="Output audio format (e.g. 'mp3', 'wav', 'flac', 'aac', 'opus').")
    codec: Optional[str] = Field(default=None, description="Audio codec (e.g. 'libmp3lame', 'aac', 'libopus', 'flac').")
    bitrate: Optional[str] = Field(default=None, description="Audio bitrate (e.g. '128k', '192k', '320k').")
    track: Optional[Union[str, int]] = Field(default=None, description="Audio track index for multi-track sources (e.g. 0, 1).")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input sources per batch.")
