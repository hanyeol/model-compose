from typing import Union, Optional, List, Dict, Any
from pydantic import Field, model_validator
from .common import CommonActionConfig
from .media import VideoAudioEncodingConfig

class VideoEncoderActionConfig(CommonActionConfig):
    video: Optional[Union[str, List[str]]] = Field(default=None, description="Existing video source(s). Mutually exclusive with 'frames'.")
    frames: Optional[Union[str, List[str]]] = Field(default=None, description="Frame sequence(s) to encode. Mutually exclusive with 'video'.")
    frame_rate: Optional[Union[int, str]] = Field(default=None, description="Frame rate for 'frames' input.")
    audio: Optional[Union[str, List[str]]] = Field(default=None, description="Optional audio source(s) to mux into the output.")
    encoding: Optional[VideoAudioEncodingConfig] = Field(default=None, description="Video/audio encoding settings.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of inputs per batch.")
    streaming: Union[bool, str] = Field(default=False, description="Whether to stream the encoded output as bytes instead of writing to a temporary file.")

    @model_validator(mode="before")
    def validate_video_or_frames(cls, values: Dict[str, Any]):
        if bool(values.get("video")) == bool(values.get("frames")):
            raise ValueError("Either 'video' or 'frames' must be set, but not both")
        if values.get("video") and values.get("frame_rate") is not None:
            raise ValueError("'frame_rate' is only valid with 'frames' input")
        return values
