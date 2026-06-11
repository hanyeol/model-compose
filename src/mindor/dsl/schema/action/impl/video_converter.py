from typing import Union, Optional, Any
from pydantic import Field
from .common import CommonActionConfig
from .media import VideoAudioCodecConfig

class VideoConverterActionConfig(CommonActionConfig):
    video: Any = Field(..., description="Video source.")
    format: Optional[str] = Field(default=None, description="Output format (e.g. 'mp4', 'webm', 'avi', 'mkv').")
    codec: Optional[Union[str, VideoAudioCodecConfig]] = Field(default=None, description="Codec settings.")
    bitrate: Optional[str] = Field(default=None, description="Video bitrate (e.g. '2M', '5000k').")
    resolution: Optional[str] = Field(default=None, description="Output resolution (e.g. '1920x1080', '1280x720').")
    fps: Optional[str] = Field(default=None, description="Output frame rate (e.g. '30', '60').")
