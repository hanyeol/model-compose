from typing import Union, Optional, List, Dict, Any
from pydantic import Field, model_validator
from ...common import CommonActionConfig
from ...media import VideoAudioEncodingConfig

class CommonRtmpPublisherActionConfig(CommonActionConfig):
    url: Union[str, List[str]] = Field(..., description="RTMP endpoint URL(s). Pass a list to broadcast to multiple targets in parallel (bounded by 'batch_size').")
    video: Optional[Union[str, List[str]]] = Field(default=None, description="Existing video source(s) to publish. Mutually exclusive with 'frames'.")
    frames: Optional[Union[str, List[str]]] = Field(default=None, description="Frame sequence(s) to publish. Mutually exclusive with 'video'.")
    frame_rate: Optional[Union[int, str]] = Field(default=None, description="Frame rate for 'frames' input.")
    audio: Optional[Union[str, List[str]]] = Field(default=None, description="Audio source(s) to publish.")
    encoding: Optional[VideoAudioEncodingConfig] = Field(default=None, description="Video/audio encoding settings. Defaults to flv container with h264/aac codecs (RTMP standard).")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of inputs per batch.")

    @model_validator(mode="before")
    def validate_inputs(cls, values: Dict[str, Any]):
        if values.get("video") and values.get("frames"):
            raise ValueError("Cannot specify both 'video' and 'frames'; choose one.")
        if not any(values.get(key) for key in ("audio", "video", "frames")):
            raise ValueError("At least one of 'audio', 'video', or 'frames' must be provided.")
        if values.get("video") and values.get("frame_rate") is not None:
            raise ValueError("'frame_rate' is only valid with 'frames' input.")
        return values
