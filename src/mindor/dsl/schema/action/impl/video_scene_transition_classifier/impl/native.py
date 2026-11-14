from typing import Union, Literal, Annotated
from pydantic import Field
from .common import CommonVideoSceneTransitionClassifierActionConfig, VideoSceneTransitionClassifierMode

class NativeVideoSceneTransitionClassifierMode(VideoSceneTransitionClassifierMode):
    CLASSIFY = "classify"

class ClassifyVideoSceneTransitionClassifierActionConfig(CommonVideoSceneTransitionClassifierActionConfig):
    mode: Literal[NativeVideoSceneTransitionClassifierMode.CLASSIFY]
    analysis_width: Union[int, str] = Field(default=96, description="Width in pixels the frames are resampled to before measuring transition signals (16-4096).")
    window_size: Union[int, str] = Field(default=5, description="Number of frames sampled on each side of a boundary; cut needs 1-2, dissolve/fade need 5+ (1-64).")
    cut_mad_threshold: Union[float, str] = Field(default=20.0, description="Mean absolute luma difference across the boundary pair above which a cut is considered.")
    dissolve_blend_threshold: Union[float, str] = Field(default=2.0, description="Maximum mean residual of the linear-blend fit for a boundary to be classified as a dissolve.")
    fade_black_threshold: Union[float, str] = Field(default=16.0, description="Mean luma below which a frame counts as a black end of a fade.")
    fade_ramp_min_slope: Union[float, str] = Field(default=2.0, description="Minimum per-frame luma slope for a boundary window to be classified as a fade.")

NativeVideoSceneTransitionClassifierActionConfig = Annotated[
    Union[
        ClassifyVideoSceneTransitionClassifierActionConfig,
    ],
    Field(discriminator="mode")
]
