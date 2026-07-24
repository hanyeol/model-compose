from typing import Optional, Dict, Any
from pydantic import Field, model_validator
from ...common import CommonActionConfig
from ...media import VideoAudioEncodingConfig

class CommonRtmpPublisherActionConfig(CommonActionConfig):
    url: str = Field(..., description="RTMP endpoint URL.")
    video: Optional[str] = Field(default=None, description="Video source to publish. A single value runs one-shot; a list or async iterator triggers continuous (persistent RTMP) mode.")
    audio: Optional[str] = Field(default=None, description="Audio source to publish. A single value runs one-shot; a list or async iterator triggers continuous mode.")
    encoding: Optional[VideoAudioEncodingConfig] = Field(default=None, description="Video/audio encoding settings. Defaults to flv container with h264/aac codecs (RTMP standard).")

    @model_validator(mode="before")
    def validate_inputs(cls, values: Dict[str, Any]):
        if not any(values.get(key) for key in ("audio", "video")):
            raise ValueError("At least one of 'audio' or 'video' must be provided.")
        return values
