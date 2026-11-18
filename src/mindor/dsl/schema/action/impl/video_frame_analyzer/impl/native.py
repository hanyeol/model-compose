from typing import Union, Literal, Annotated
from pydantic import Field
from .common import CommonVideoFrameAnalyzerActionConfig, VideoFrameAnalyzerMetric

class NativeVideoFrameAnalyzerMetric(VideoFrameAnalyzerMetric):
    TEMPORAL_NOISE   = "temporal-noise"
    PAIR_DIFFERENCE  = "pair-difference"
    ZERO_PIXEL_RATIO = "zero-pixel-ratio"

class TemporalNoiseVideoFrameAnalyzerActionConfig(CommonVideoFrameAnalyzerActionConfig):
    metric: Literal[NativeVideoFrameAnalyzerMetric.TEMPORAL_NOISE]
    analysis_width: Union[int, str] = Field(default=96, description="Width in pixels the frames are resampled to before measuring inter-frame noise; smaller values speed up long sequences (16-4096).")

class PairDifferenceVideoFrameAnalyzerActionConfig(CommonVideoFrameAnalyzerActionConfig):
    metric: Literal[NativeVideoFrameAnalyzerMetric.PAIR_DIFFERENCE]
    analysis_width: Union[int, str] = Field(default=96, description="Width in pixels the frames are resampled to before measuring pair differences (16-4096).")
    move_threshold: Union[float, str] = Field(default=2.0, description="Mean absolute luma difference above which a frame pair counts as moving.")

class ZeroPixelRatioVideoFrameAnalyzerActionConfig(CommonVideoFrameAnalyzerActionConfig):
    metric: Literal[NativeVideoFrameAnalyzerMetric.ZERO_PIXEL_RATIO]
    analysis_width: Union[int, str] = Field(default=96, description="Width in pixels the frames are resampled to before counting unchanged pixels (16-4096).")
    exact_match: Union[bool, str] = Field(default=True, description="When true, a pixel counts as zero only when identical between frames; when false, pixels whose absolute difference is below 1 (post-quantization) count as zero.")

NativeVideoFrameAnalyzerActionConfig = Annotated[
    Union[
        TemporalNoiseVideoFrameAnalyzerActionConfig,
        PairDifferenceVideoFrameAnalyzerActionConfig,
        ZeroPixelRatioVideoFrameAnalyzerActionConfig,
    ],
    Field(discriminator="metric")
]
