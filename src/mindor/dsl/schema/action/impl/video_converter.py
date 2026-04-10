from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from .common import CommonActionConfig

class VideoConverterActionConfig(CommonActionConfig):
    video: str = Field(..., description="Video file path or variable reference.")
    format: Optional[Union[str, None]] = Field(default=None, description="Output format (e.g. 'mp4', 'webm', 'avi', 'mkv').")
    codec: Optional[Union[str, None]] = Field(default=None, description="Video codec (e.g. 'libx264', 'libx265', 'vp9').")
    audio_codec: Optional[Union[str, None]] = Field(default=None, description="Audio codec (e.g. 'aac', 'opus', 'mp3').")
    bitrate: Optional[Union[str, None]] = Field(default=None, description="Video bitrate (e.g. '2M', '5000k').")
    resolution: Optional[Union[str, None]] = Field(default=None, description="Output resolution (e.g. '1920x1080', '1280x720').")
    fps: Optional[Union[str, None]] = Field(default=None, description="Output frame rate (e.g. '30', '60').")
