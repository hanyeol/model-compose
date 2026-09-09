from typing import Union, Optional
from pydantic import BaseModel, Field

class VideoEncoderConfig(BaseModel):
    codec: Optional[str] = Field(default=None, description="Video codec (e.g., libx264, libx265, libvpx-vp9).")
    bitrate: Optional[str] = Field(default=None, description="Target video bitrate (e.g., 2M, 5000k). Ignored when `quality` is set.")
    quality: Optional[Union[int, str]] = Field(default=None, description="Quality target to hold while the bitrate floats, sent to the encoder as a constant rate factor (0-51 for x264/x265, lower is better; 18 is near-transparent). This scale runs opposite to the 0-100 quality that image and screenshot actions take. Takes precedence over `bitrate`.")
    resolution: Optional[str] = Field(default=None, description="Output video resolution (e.g., 1920x1080, 1280x720).")
    fps: Optional[Union[str, int, float]] = Field(default=None, description="Output video frame rate in frames per second.")

class AudioEncoderConfig(BaseModel):
    codec: Optional[str] = Field(default=None, description="Audio codec (e.g., aac, libopus, libmp3lame).")
    bitrate: Optional[str] = Field(default=None, description="Target audio bitrate (e.g., 128k, 192k).")
    sample_rate: Optional[Union[int, str]] = Field(default=None, description="Output audio sample rate in Hz.")
    channels: Optional[Union[int, str]] = Field(default=None, description="Output channel count (e.g., 1 for mono, 2 for stereo).")

class VideoAudioEncodingConfig(BaseModel):
    format: Optional[str] = Field(default=None, description="Output container format (e.g., mp4, webm, mkv).")
    video: Optional[VideoEncoderConfig] = Field(default=None, description="Video encoder settings for the output.")
    audio: Optional[AudioEncoderConfig] = Field(default=None, description="Audio encoder settings for the output.")
