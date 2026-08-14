from typing import Union, Optional, List, Dict, Any
from pydantic import Field, model_validator
from .common import CommonActionConfig
from .media import VideoAudioEncodingConfig

class VideoEncoderActionConfig(CommonActionConfig):
    video: Optional[Union[List[str], str]] = Field(default=None, description="Existing video source or list of sources. Mutually exclusive with `frames`.")
    frames: Optional[Union[List[str], str]] = Field(default=None, description="Frame sequence or list of sequences to encode. Mutually exclusive with `video`.")
    frame_rate: Optional[Union[int, str]] = Field(default=None, description="Frame rate applied when encoding from `frames`.")
    audio: Optional[Union[str, List[str]]] = Field(default=None, description="Audio source or list of sources muxed into the output.")
    encoding: Optional[VideoAudioEncodingConfig] = Field(default=None, description="Encoding settings applied to the output video and audio.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of inputs processed per batch.")
    streaming: Union[bool, str] = Field(default=False, description="Whether the encoded output is emitted as a byte stream instead of a temporary file.")

    @model_validator(mode="before")
    def validate_video_or_frames(cls, values: Dict[str, Any]):
        if bool(values.get("video")) == bool(values.get("frames")):
            raise ValueError("Either 'video' or 'frames' must be set, but not both")
        if values.get("video") and values.get("frame_rate") is not None:
            raise ValueError("'frame_rate' is only valid with 'frames' input")
        return values
