from typing import Union
from pydantic import Field
from .common import CommonVideoSceneTransitionClassifierActionConfig

class NativeVideoSceneTransitionClassifierActionConfig(CommonVideoSceneTransitionClassifierActionConfig):
    downsample_width: Union[int, str] = Field(default=96, description="Width in pixels the frames are resampled to before measuring transition signals (16-4096).")
    window_size: Union[int, str] = Field(default=15, description="Upper bound on frames sampled on each side of a boundary; the analysis span auto-narrows within it to the actual transition ramp (1-64).")
    cut_mad_threshold: Union[float, str] = Field(default=20.0, description="Mean absolute luma difference across the boundary pair above which a cut is considered.")
    dissolve_blend_threshold: Union[float, str] = Field(default=0.25, description="Maximum median scale-normalized residual of the linear-blend fit for a boundary to be classified as a dissolve (0.0-1.0; smaller = stricter).")
    fade_black_threshold: Union[float, str] = Field(default=45.0, description="Mean luma below which the window's flat frame reads as a fade through black.")
    fade_white_threshold: Union[float, str] = Field(default=210.0, description="Mean luma above which the window's flat frame reads as a fade through white.")
    fade_ramp_min_slope: Union[float, str] = Field(default=2.0, description="Minimum per-frame luma slope for a boundary window to be classified as a fade.")
    flash_peak_threshold: Union[float, str] = Field(default=170.0, description="Minimum peak frame mean luma for a boundary to be classified as a flash (bright burst between two normal shots).")
    flash_endpoint_gap: Union[float, str] = Field(default=50.0, description="Minimum gap between the peak frame and the brighter endpoint for a boundary to be classified as a flash.")
    wipe_edge_threshold: Union[float, str] = Field(default=0.38, description="Maximum relative residual of the straight-edge fit for a boundary to be classified as a wipe or slide (0.0-1.0; smaller = stricter).")
    wipe_region_pure_threshold: Union[float, str] = Field(default=0.6, description="Minimum share of block-wise 'pure old or pure new' agreement for a wipe pattern that is not a straight edge (iris, center-out).")
    blur_detail_ratio: Union[float, str] = Field(default=0.5, description="Maximum ratio of inside-window detail to endpoint detail for a boundary to be classified as blur (0.0-1.0; smaller = stricter, 0.5 = inside has at most half the gradient of a sharp endpoint).")
    jump_block_min_std: Union[float, str] = Field(default=4.0, description="Minimum luma standard deviation inside a block for that block to contribute to the same-structure (jump) check; flatter blocks have no detail to line up.")
    jump_block_correlation: Union[float, str] = Field(default=0.6, description="Minimum brightness-normalized correlation per block for the block to count as structurally matching, used to distinguish a jump (same shot, lighting change) from a cut (0.0-1.0).")
    jump_min_matching_blocks: Union[int, str] = Field(default=6, description="Minimum number of detailed blocks required before the same-structure gate is trusted; too few detailed blocks fall back to cut (1-64).")
    jump_min_match_ratio: Union[float, str] = Field(default=0.5, description="Minimum share of detailed blocks that must structurally match for the boundary to be classified as a jump instead of a cut (0.0-1.0).")
