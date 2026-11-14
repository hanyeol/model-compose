from typing import Union, Literal, Annotated
from pydantic import Field
from .common import CommonVideoFrameAnalyzerActionConfig, VideoFrameAnalyzerMetric

class OpenCvVideoFrameAnalyzerMetric(VideoFrameAnalyzerMetric):
    MOVING_PAIRS = "moving_pairs"
    DUPLICATE    = "duplicate"
    SHARPNESS    = "sharpness"

class MovingPairsVideoFrameAnalyzerActionConfig(CommonVideoFrameAnalyzerActionConfig):
    metric: Literal[OpenCvVideoFrameAnalyzerMetric.MOVING_PAIRS]
    analysis_width: Union[int, str] = Field(default=96, description="Width in pixels the frames are resampled to before measuring motion (16-4096).")
    change_threshold: Union[float, str] = Field(default=6.0, description="Per-pixel absolute luma difference above which a pixel counts as changed.")
    moving_share_threshold: Union[float, str] = Field(default=0.01, description="Minimum share of changed pixels for a frame pair to count as moving (0.0-1.0).")

class DuplicateVideoFrameAnalyzerActionConfig(CommonVideoFrameAnalyzerActionConfig):
    metric: Literal[OpenCvVideoFrameAnalyzerMetric.DUPLICATE]
    analysis_width: Union[int, str] = Field(default=96, description="Width in pixels the frames are resampled to before detecting duplicate frames (16-4096).")
    duplicate_threshold: Union[float, str] = Field(default=0.5, description="Mean absolute luma difference below which two consecutive frames count as duplicates.")
    max_period: Union[int, str] = Field(default=8, description="Largest duplicate-pattern period searched for (frames); covers the 24/25 fps -> 30 fps pulldowns and common cadences (2-32).")

class SharpnessVideoFrameAnalyzerActionConfig(CommonVideoFrameAnalyzerActionConfig):
    metric: Literal[OpenCvVideoFrameAnalyzerMetric.SHARPNESS]
    analysis_width: Union[int, str] = Field(default=96, description="Width in pixels the frames are resampled to before measuring sharpness per frame (16-4096).")
    max_period: Union[int, str] = Field(default=8, description="Largest sharpness-oscillation period searched for via autocorrelation (frames); covers common frame-interpolation cadences (2-32).")

OpenCvVideoFrameAnalyzerActionConfig = Annotated[
    Union[
        MovingPairsVideoFrameAnalyzerActionConfig,
        DuplicateVideoFrameAnalyzerActionConfig,
        SharpnessVideoFrameAnalyzerActionConfig,
    ],
    Field(discriminator="metric")
]
