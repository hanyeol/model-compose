from typing import Union
from pydantic import Field
from .native import NativeVideoSceneTransitionClassifierActionConfig

class OpenCvVideoSceneTransitionClassifierActionConfig(NativeVideoSceneTransitionClassifierActionConfig):
    motion_max_features: Union[int, str] = Field(default=80, description="Maximum number of feature points tracked per frame pair for affine motion estimation (16-2000).")
    motion_feature_quality: Union[float, str] = Field(default=0.01, description="Minimum quality level passed to goodFeaturesToTrack (0.0-1.0).")
    motion_feature_min_distance: Union[float, str] = Field(default=4.0, description="Minimum pixel distance between feature points at analysis resolution.")
    motion_ransac_threshold: Union[float, str] = Field(default=2.0, description="Maximum reprojection error (analysis-resolution pixels) for a feature correspondence to count as a RANSAC inlier.")
    motion_min_inlier_ratio: Union[float, str] = Field(default=0.5, description="Minimum inlier ratio for a pair's affine estimate to be trusted (0.0-1.0).")
    motion_calm_path_limit: Union[float, str] = Field(default=0.3, description="Maximum summed camera path (share of frame) below which the window reads as calm — glitch detection gate.")
    motion_calm_zoom_limit: Union[float, str] = Field(default=0.3, description="Maximum summed |log scale| below which the window reads as calm — glitch detection gate.")
    motion_calm_rotation_limit: Union[float, str] = Field(default=20.0, description="Maximum summed |rotation| (degrees) below which the window reads as calm — glitch detection gate.")
    spin_min_rotation_degrees: Union[float, str] = Field(default=25.0, description="Minimum summed |rotation| (degrees) for a boundary to be classified as spin.")
    spin_turn_share: Union[float, str] = Field(default=0.7, description="Minimum share of rotation that must be signed (same direction) for a boundary to be classified as spin (0.0-1.0).")
    zoom_min_scale_change: Union[float, str] = Field(default=0.5, description="Minimum summed |log scale| for a boundary to be classified as zoom.")
    whip_min_net_share: Union[float, str] = Field(default=0.3, description="Minimum net camera displacement (share of frame) for a boundary to be classified as whip.")
    whip_max_path_ratio: Union[float, str] = Field(default=1.5, description="Maximum ratio of total path to net displacement — whip travels mostly in one direction, so path/net must stay below this.")
    whip_max_detail_ratio: Union[float, str] = Field(default=0.7, description="Maximum per-axis inside/endpoint gradient ratio — whip motion-blurs the inside, so detail must fall below this (0.0-1.0).")
    shake_min_path_share: Union[float, str] = Field(default=0.4, description="Minimum summed camera path (share of frame) for a boundary to be classified as shake.")
    shake_min_path_net_ratio: Union[float, str] = Field(default=3.0, description="Minimum ratio of total path to net displacement — shake oscillates, so path/net must exceed this.")
    shake_min_tracked_pairs: Union[int, str] = Field(default=3, description="Minimum number of frame pairs with a tracked affine estimate for shake to be reported (1-64).")
    glitch_min_back_swings: Union[int, str] = Field(default=2, description="Minimum number of back-swings (progress curve reversing) for a boundary to be classified as glitch (1-64).")
    glitch_min_hard_switches: Union[int, str] = Field(default=2, description="Alternative gate: a single back-swing plus this many hard switches inside the window also reads as glitch (1-64).")
