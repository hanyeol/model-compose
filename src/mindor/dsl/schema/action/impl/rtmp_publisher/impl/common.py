from typing import Optional, Dict, Any
from pydantic import Field, model_validator
from ...common import CommonActionConfig
from ...media import VideoAudioEncodingConfig

class CommonRtmpPublisherActionConfig(CommonActionConfig):
    url: str = Field(..., description="Full URL of the RTMP endpoint (e.g., rtmp://host/app/stream).")
    video: Optional[str] = Field(default=None, description="Video source published to the RTMP endpoint; a single value runs one-shot, a list or async iterator publishes continuously.")
    audio: Optional[str] = Field(default=None, description="Audio source published to the RTMP endpoint; a single value runs one-shot, a list or async iterator publishes continuously.")
    encoding: Optional[VideoAudioEncodingConfig] = Field(default=None, description="Encoding settings applied to the published video and audio; defaults to the RTMP-standard flv container with h264/aac codecs.")

    @model_validator(mode="before")
    def validate_inputs(cls, values: Dict[str, Any]):
        if not any(values.get(key) for key in ("audio", "video")):
            raise ValueError("At least one of 'audio' or 'video' must be provided.")
        return values
