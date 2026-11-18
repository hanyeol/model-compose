from typing import Union, Literal, Annotated
from pydantic import Field
from .common import CommonVideoFrameAnalyzerActionConfig, VideoFrameAnalyzerMetric

class OpenCvVideoFrameAnalyzerMetric(VideoFrameAnalyzerMetric):
    MOVING_PAIRS = "moving-pairs"
    DUPLICATE    = "duplicate"
    SHARPNESS    = "sharpness"
    PICTURE_BOX  = "picture-box"
    PALETTE      = "palette"

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

class PictureBoxVideoFrameAnalyzerActionConfig(CommonVideoFrameAnalyzerActionConfig):
    metric: Literal[OpenCvVideoFrameAnalyzerMetric.PICTURE_BOX]
    analysis_width: Union[int, str] = Field(default=320, description="Width in pixels the frames are resampled to before measuring the picture box (64-4096).")
    sample_count: Union[int, str] = Field(default=24, description="Number of frames evenly sampled across the sequence; a sampled max exposes lit areas across the shot so steady dark bars stand out from momentarily dark pictures (4-256).")
    lit_threshold: Union[float, str] = Field(default=24.0, description="Minimum grayscale value above which a pixel counts as lit (0.0-255.0).")
    picture_lit_share: Union[float, str] = Field(default=0.6, description="Minimum share of frames a row or column must stay lit in to count as inside the picture (0.0-1.0).")
    bar_dark_share: Union[float, str] = Field(default=0.1, description="Maximum median lit share outside the picture for the surrounding region to count as a dark bar (0.0-1.0).")
    bar_min_share: Union[float, str] = Field(default=0.06, description="Minimum share of frame height / width the surrounding bars must occupy to be reported (0.0-1.0).")
    picture_edge_lit_share: Union[float, str] = Field(default=0.8, description="Minimum lit share right on the picture's outermost row / column; keeps noisy textures from being counted as a bordered picture (0.0-1.0).")
    min_picture_fraction: Union[float, str] = Field(default=0.2, description="Minimum share of frame height and width the picture must retain to be reported (0.0-1.0).")

class PaletteVideoFrameAnalyzerActionConfig(CommonVideoFrameAnalyzerActionConfig):
    metric: Literal[OpenCvVideoFrameAnalyzerMetric.PALETTE]
    analysis_width: Union[int, str] = Field(default=96, description="Width in pixels the frames are resampled to before k-means clustering (16-4096).")
    sample_count: Union[int, str] = Field(default=8, description="Number of frames evenly sampled across the sequence and stacked for a shot-wide palette (1-256).")
    max_colours: Union[int, str] = Field(default=8, description="Maximum number of colour clusters extracted via k-means (1-32).")
    min_share: Union[float, str] = Field(default=0.01, description="Minimum share of pixels a colour must claim to be reported (0.0-1.0).")

OpenCvVideoFrameAnalyzerActionConfig = Annotated[
    Union[
        MovingPairsVideoFrameAnalyzerActionConfig,
        DuplicateVideoFrameAnalyzerActionConfig,
        SharpnessVideoFrameAnalyzerActionConfig,
        PictureBoxVideoFrameAnalyzerActionConfig,
        PaletteVideoFrameAnalyzerActionConfig,
    ],
    Field(discriminator="metric")
]
