from typing import Union, Optional
from pydantic import Field
from .common import CommonActionConfig
from .media import VideoSourceConfig

class VideoConverterActionConfig(CommonActionConfig):
    video: Union[str, VideoSourceConfig] = Field(..., description="Video source: file path or variable reference, or VideoSourceConfig with format hints for raw or headerless video.")
    format: Optional[str] = Field(default=None, description="Output format (e.g. 'mp4', 'webm', 'avi', 'mkv').")
    codec: Optional[str] = Field(default=None, description="Video codec (e.g. 'libx264', 'libx265', 'vp9').")
    audio_codec: Optional[str] = Field(default=None, description="Audio codec (e.g. 'aac', 'opus', 'mp3').")
    bitrate: Optional[str] = Field(default=None, description="Video bitrate (e.g. '2M', '5000k').")
    resolution: Optional[str] = Field(default=None, description="Output resolution (e.g. '1920x1080', '1280x720').")
    fps: Optional[str] = Field(default=None, description="Output frame rate (e.g. '30', '60').")
