from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field, model_validator
from .common import CommonActionConfig

class VideoSourceConfig(BaseModel):
    path: Optional[str] = Field(default=None, description="Video file path or variable reference. Use when the source is a file.")
    data: Optional[Any] = Field(default=None, description="Raw video data as bytes, stream, or variable reference. Use when the source is not a file (e.g. raw binary stream).")
    format: Optional[str] = Field(default=None, description="Input format hint for raw or headerless video (e.g. 'rawvideo', 'h264', 'mjpeg'). Required when ffmpeg cannot auto-detect the format.")
    resolution: Optional[str] = Field(default=None, description="Input resolution, required for raw video (e.g. '1920x1080').")
    fps: Optional[str] = Field(default=None, description="Input frame rate, required for raw video (e.g. '30').")
    pixel_format: Optional[str] = Field(default=None, description="Input pixel format, required for raw video (e.g. 'yuv420p', 'rgb24').")

    @model_validator(mode="after")
    def validate_source(self):
        if not self.path and not self.data:
            raise ValueError("Either 'path' or 'data' must be specified in VideoSourceConfig.")
        return self

class VideoConverterActionConfig(CommonActionConfig):
    source: Union[str, VideoSourceConfig] = Field(..., description="Video file path, or VideoSourceConfig with format hints for raw or headerless video.")
    format: Optional[str] = Field(default=None, description="Output format (e.g. 'mp4', 'webm', 'avi', 'mkv').")
    codec: Optional[str] = Field(default=None, description="Video codec (e.g. 'libx264', 'libx265', 'vp9').")
    audio_codec: Optional[str] = Field(default=None, description="Audio codec (e.g. 'aac', 'opus', 'mp3').")
    bitrate: Optional[str] = Field(default=None, description="Video bitrate (e.g. '2M', '5000k').")
    resolution: Optional[str] = Field(default=None, description="Output resolution (e.g. '1920x1080', '1280x720').")
    fps: Optional[str] = Field(default=None, description="Output frame rate (e.g. '30', '60').")
