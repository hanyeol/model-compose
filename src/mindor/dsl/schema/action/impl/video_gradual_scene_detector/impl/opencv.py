from typing import Union, List
from pydantic import Field
from .common import CommonVideoGradualSceneDetectorActionConfig

class OpenCvVideoGradualSceneDetectorActionConfig(CommonVideoGradualSceneDetectorActionConfig):
    downsample_width: Union[int, str] = Field(default=96, description="Width in pixels the frames are resampled to before scanning for gradual transitions (16-4096).")
    window_lengths: Union[List[Union[float, str]], str] = Field(default=[ "200ms", "350ms", "600ms", "1s", "1.5s" ], description="Candidate window lengths the scanner tries at each position, as seconds or duration strings (e.g. \"200ms\").")
    plateau_share: Union[float, str] = Field(default=0.3, description="Maximum ratio of 'just-outside-the-window' change to 'across-the-window' change for the two ends to count as steady (0.0-1.0).")
    min_changed_share: Union[float, str] = Field(default=0.5, description="Minimum share of the 6x8 block grid that must differ between window ends for the pair to count as different pictures (0.0-1.0).")
    endpoint_min_std: Union[float, str] = Field(default=12.0, description="Minimum luma standard deviation at each window end; flatter ends count as empty-page fades, not shot changes.")
    endpoint_diff_threshold: Union[float, str] = Field(default=10.0, description="Minimum low-resolution mean absolute luma difference between the two window ends for the window to be considered at all.")
    motion_warp_threshold: Union[float, str] = Field(default=0.45, description="Maximum ratio of post-warp residual to pre-warp residual for optical-flow warp to 'explain' the change (gate for pan / zoom inside one take).")
