from typing import Union, Optional, List, Any
from pydantic import Field, model_validator
from ..common import CommonHumanMeshRecoveryParamsConfig, CommonHumanMeshRecoveryModelActionConfig

class GVHMRHumanMeshRecoveryParamsConfig(CommonHumanMeshRecoveryParamsConfig):
    static_camera: Union[bool, str] = Field(default=False, description="Whether to treat the input as captured from a static camera; disables camera trajectory estimation.")

class GVHMRHumanMeshRecoveryModelActionConfig(CommonHumanMeshRecoveryModelActionConfig):
    frames: Union[Any, List[Any], List[List[Any]], str] = Field(..., description="Frame images to analyze; a single frame, flat list, list of batches, or stream of batches.")
    timestamps: Optional[Union[float, List[float], List[List[float]], str]] = Field(default=None, description="Per-frame timestamps in seconds paired with `frames`; overrides `frame_rate`/`time_offset` when set.")
    frame_rate: Optional[Union[float, str]] = Field(default=None, description="Frames per second; required when `timestamps` is unset to derive per-frame timestamps.")
    time_offset: Union[Union[str, float, int], List[Union[str, float, int]], str] = Field(default=0.0, description="Timestamp offset in seconds for the first frame of each batch; scalar values broadcast, lists pair per batch.")
    batch_size: Union[int, str] = Field(default=1, description="Number of frame sequences processed per iteration.")
    params: GVHMRHumanMeshRecoveryParamsConfig = Field(default_factory=GVHMRHumanMeshRecoveryParamsConfig, description="GVHMR recovery parameters.")

    @model_validator(mode="after")
    def validate_timestamps_or_frame_rate(self):
        if self.timestamps is None and self.frame_rate is None:
            raise ValueError("Either 'timestamps' or 'frame_rate' must be set.")
        return self
