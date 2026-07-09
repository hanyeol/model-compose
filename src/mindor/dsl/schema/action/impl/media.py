from typing import Union, Optional
from pydantic import BaseModel, Field

class VideoEncoderConfig(BaseModel):
    codec: Optional[str] = Field(default=None, description="Video codec (e.g. 'libx264', 'libx265', 'libvpx-vp9').")
    bitrate: Optional[str] = Field(default=None, description="Video bitrate (e.g. '2M', '5000k').")
    resolution: Optional[str] = Field(default=None, description="Video resolution (e.g. '1920x1080', '1280x720').")
    fps: Optional[Union[str, int, float]] = Field(default=None, description="Video frame rate (e.g. '30', '60').")

class AudioEncoderConfig(BaseModel):
    codec: Optional[str] = Field(default=None, description="Audio codec (e.g. 'aac', 'libopus', 'libmp3lame').")
    bitrate: Optional[str] = Field(default=None, description="Audio bitrate (e.g. '128k', '192k').")

class VideoAudioEncodingConfig(BaseModel):
    format: Optional[str] = Field(default=None, description="Container format (e.g. 'mp4', 'webm', 'mkv').")
    video: Optional[VideoEncoderConfig] = Field(default=None, description="Video encoder settings.")
    audio: Optional[AudioEncoderConfig] = Field(default=None, description="Audio encoder settings.")
