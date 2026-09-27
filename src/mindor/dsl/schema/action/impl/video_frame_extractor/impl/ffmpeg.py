from typing import Union
from pydantic import Field
from .common import CommonVideoFrameExtractorActionConfig

class FFmpegVideoFrameExtractorActionConfig(CommonVideoFrameExtractorActionConfig):
    keyframe_only: Union[bool, str] = Field(default=False, description="Whether to extract only I-frames (keyframes).")
    frame_interval: Union[int, str] = Field(default=1, description="Sampling stride applied to frames, or to keyframes when `keyframe_only` is true.")
