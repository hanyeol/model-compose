from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from .common import CommonActionConfig

class AudioExtractorActionConfig(CommonActionConfig):
    source: str = Field(..., description="Source file path or variable reference (video or audio).")
    format: Optional[str] = Field(default=None, description="Output audio format (e.g. 'mp3', 'wav', 'flac', 'aac', 'opus').")
    codec: Optional[str] = Field(default=None, description="Audio codec (e.g. 'libmp3lame', 'aac', 'libopus', 'flac').")
    bitrate: Optional[str] = Field(default=None, description="Audio bitrate (e.g. '128k', '192k', '320k').")
    track: Optional[Union[str, int]] = Field(default=None, description="Audio track index for multi-track sources (e.g. 0, 1).")
