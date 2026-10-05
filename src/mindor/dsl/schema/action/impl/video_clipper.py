from typing import Union, Optional, List
from enum import Enum
from pydantic import Field
from mindor.dsl.schema.common.media import MediaClipSpanConfig
from .common import CommonActionConfig

class VideoClipperPrecision(str, Enum):
    FAST     = "fast"
    ACCURATE = "accurate"

class VideoClipperActionConfig(CommonActionConfig):
    video: Union[List[str], str] = Field(..., description="Video source to clip.")
    span: Union[List[MediaClipSpanConfig], MediaClipSpanConfig, str] = Field(..., description="Time span(s) to clip from each video.")
    merge: Union[bool, str] = Field(default=False, description="Whether to concatenate all clips per source into a single video.")
    precision: Union[VideoClipperPrecision, str] = Field(default=VideoClipperPrecision.FAST, description="Cut precision.")
    return_timestamp: Union[bool, str] = Field(default=False, description="Whether each clip carries its actual cut span alongside the video.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input sources processed per batch.")
