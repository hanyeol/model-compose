from typing import Union, Optional, Any
from pydantic import BaseModel, Field

class ImageSourceConfig(BaseModel):
    data: Any = Field(..., description="Image data: file path string, raw bytes, stream, or variable reference (e.g. ${input.image as file}).")
    format: Optional[str] = Field(default=None, description="Input format hint for raw or headerless image (e.g. 'raw', 'rgb', 'rgba'). Required when the format cannot be auto-detected.")
    resolution: Optional[str] = Field(default=None, description="Input resolution, required for raw image (e.g. '1920x1080').")
    pixel_format: Optional[str] = Field(default=None, description="Input pixel format, required for raw image (e.g. 'rgb24', 'rgba', 'yuv420p').")
    mode: Optional[str] = Field(default=None, description="PIL image mode hint (e.g. 'RGB', 'RGBA', 'L'). Used when decoding raw pixel data.")

class AudioSourceConfig(BaseModel):
    data: Any = Field(..., description="Audio data: file path string, raw bytes, stream, or variable reference (e.g. ${input.audio as file}).")
    format: Optional[str] = Field(default=None, description="Input format hint for raw or headerless audio (e.g. 's16le', 'f32le', 'mulaw'). Required when ffmpeg cannot auto-detect the format.")
    sample_rate: Optional[Union[int, str]] = Field(default=None, description="Input sample rate in Hz, required for raw audio (e.g. 22050, 44100).")
    channels: Optional[Union[int, str]] = Field(default=None, description="Input number of channels, required for raw audio (e.g. 1 for mono, 2 for stereo).")

class VideoSourceConfig(BaseModel):
    data: Any = Field(..., description="Video data: file path string, raw bytes, stream, or variable reference (e.g. ${input.video as file}).")
    format: Optional[str] = Field(default=None, description="Input format hint for raw or headerless video (e.g. 'rawvideo', 'h264', 'mjpeg'). Required when ffmpeg cannot auto-detect the format.")
    resolution: Optional[str] = Field(default=None, description="Input resolution, required for raw video (e.g. '1920x1080').")
    fps: Optional[str] = Field(default=None, description="Input frame rate, required for raw video (e.g. '30').")
    pixel_format: Optional[str] = Field(default=None, description="Input pixel format, required for raw video (e.g. 'yuv420p', 'rgb24').")
