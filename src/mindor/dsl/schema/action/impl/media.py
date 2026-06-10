from typing import Optional, Any
from pydantic import BaseModel, Field

class VideoAudioCodecConfig(BaseModel):
    video: Optional[str] = Field(default=None, description="Video codec (e.g. 'libx264', 'libx265', 'libvpx-vp9').")
    audio: Optional[str] = Field(default=None, description="Audio codec (e.g. 'aac', 'libopus', 'libmp3lame').")
