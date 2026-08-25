from typing import Union, Literal, Optional, List
from enum import Enum
from pydantic import Field
from ...common import CommonActionConfig

class VideoAnalyzerMetric(str, Enum):
    BLACK      = "black"
    FREEZE     = "freeze"
    BRIGHTNESS = "brightness"
    MOTION     = "motion"

class CommonVideoAnalyzerActionConfig(CommonActionConfig):
    metric: VideoAnalyzerMetric = Field(..., description="Kind of measurement performed on the video.")
    video: Union[str, List[str]] = Field(..., description="Video source or list of sources to analyze.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input videos processed per batch.")

class VideoAnalyzerBlackActionConfig(CommonVideoAnalyzerActionConfig):
    metric: Literal[VideoAnalyzerMetric.BLACK]
    min_duration: Union[float, int, str] = Field(default="2s", description="Minimum duration a black region must last to be reported.")
    pixel_threshold: Union[float, int, str] = Field(default=0.10, description="Per-pixel luminance below which a pixel counts as black (0.0-1.0).")
    picture_threshold: Union[float, int, str] = Field(default=0.98, description="Fraction of pixels that must be black for a frame to count as black (0.0-1.0).")

class VideoAnalyzerFreezeActionConfig(CommonVideoAnalyzerActionConfig):
    metric: Literal[VideoAnalyzerMetric.FREEZE]
    min_duration: Union[float, int, str] = Field(default="2s", description="Minimum duration a freeze must last to be reported.")
    noise_threshold: Union[float, int, str] = Field(default=0.001, description="Maximum inter-frame difference (0.0-1.0) still treated as a freeze.")

class VideoAnalyzerBrightnessActionConfig(CommonVideoAnalyzerActionConfig):
    metric: Literal[VideoAnalyzerMetric.BRIGHTNESS]
    sample_rate: Union[float, int, str] = Field(default=1.0, description="Frames per second sampled for brightness statistics; lower values speed up long videos.")
    include_timeline: Union[bool, str] = Field(default=False, description="Whether per-sampled-frame brightness values are included in the result.")

class VideoAnalyzerMotionActionConfig(CommonVideoAnalyzerActionConfig):
    metric: Literal[VideoAnalyzerMetric.MOTION]
    sample_rate: Union[float, int, str] = Field(default=1.0, description="Frames per second sampled for motion estimation; lower values speed up long videos.")
    include_timeline: Union[bool, str] = Field(default=False, description="Whether per-sampled-frame motion values are included in the result.")
