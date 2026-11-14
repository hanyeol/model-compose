from typing import Union, Literal, Annotated
from pydantic import Field
from .common import CommonVideoMotionEstimatorActionConfig, VideoMotionEstimatorMode

class OpenCvVideoMotionEstimatorMode(VideoMotionEstimatorMode):
    RIGID    = "rigid"
    KENBURNS = "kenburns"

class RigidVideoMotionEstimatorActionConfig(CommonVideoMotionEstimatorActionConfig):
    mode: Literal[OpenCvVideoMotionEstimatorMode.RIGID]
    analysis_width: Union[int, str] = Field(default=320, description="Width in pixels the frames are resampled to before tracking features (64-4096).")
    max_features: Union[int, str] = Field(default=200, description="Maximum number of feature points tracked per frame pair (16-2000).")
    feature_quality: Union[float, str] = Field(default=0.01, description="Minimum quality level passed to goodFeaturesToTrack (0.0-1.0).")
    feature_min_distance: Union[float, str] = Field(default=8.0, description="Minimum pixel distance between feature points at analysis resolution.")
    ransac_threshold: Union[float, str] = Field(default=3.0, description="Maximum reprojection error (in analysis-resolution pixels) for a feature correspondence to count as a RANSAC inlier.")
    min_inliers: Union[int, str] = Field(default=10, description="Minimum inlier count required before reporting a rigid transform; below this the pair is marked as low-confidence (4-1000).")

class KenburnsVideoMotionEstimatorActionConfig(CommonVideoMotionEstimatorActionConfig):
    mode: Literal[OpenCvVideoMotionEstimatorMode.KENBURNS]
    analysis_width: Union[int, str] = Field(default=320, description="Width in pixels the frames are resampled to before tracking features (64-4096).")
    max_features: Union[int, str] = Field(default=200, description="Maximum number of feature points tracked per frame pair (16-2000).")
    feature_quality: Union[float, str] = Field(default=0.01, description="Minimum quality level passed to goodFeaturesToTrack (0.0-1.0).")
    feature_min_distance: Union[float, str] = Field(default=8.0, description="Minimum pixel distance between feature points at analysis resolution.")
    ransac_threshold: Union[float, str] = Field(default=3.0, description="Maximum reprojection error (in analysis-resolution pixels) for a feature correspondence to count as a RANSAC inlier.")
    stillness_threshold: Union[float, str] = Field(default=0.3, description="Per-frame median feature displacement (in analysis-resolution pixels) below which the content is treated as a near-static source panned by the camera.")
    rigid_inlier_floor: Union[float, str] = Field(default=0.85, description="Minimum RANSAC inlier ratio required for the pair to be considered plane-like enough for a Ken Burns reading (0.0-1.0).")

OpenCvVideoMotionEstimatorActionConfig = Annotated[
    Union[
        RigidVideoMotionEstimatorActionConfig,
        KenburnsVideoMotionEstimatorActionConfig,
    ],
    Field(discriminator="mode")
]
