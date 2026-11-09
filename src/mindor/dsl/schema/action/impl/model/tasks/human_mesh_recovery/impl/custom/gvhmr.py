from typing import Union, Optional, List, Dict, Any
from pydantic import Field, model_validator
from ..common import CommonHumanMeshRecoveryParamsConfig, CommonHumanMeshRecoveryModelActionConfig

class GVHMRHumanMeshRecoveryParamsConfig(CommonHumanMeshRecoveryParamsConfig):
    static_camera: Union[bool, str] = Field(default=False, description="Whether to treat the input as captured from a static camera; disables camera trajectory estimation.")
    focal_length: Optional[Union[float, str]] = Field(default=None, description="Full-frame-equivalent focal length in mm; None lets the pipeline estimate from frame size.")
    track_id: Optional[Union[int, str]] = Field(default=None, description="Pose-tracking track id to recover; None picks the longest track.")

class GVHMRHumanMeshRecoveryModelActionConfig(CommonHumanMeshRecoveryModelActionConfig):
    frames: Union[Any, List[Any], str] = Field(..., description="One video's ordered frame images; a flat list, stream, or reference. Reuse the frames fed to the paired pose-tracking component.")
    tracks: Union[Dict[str, Any], List[Dict[str, Any]], str] = Field(..., description="Pose-tracking detections paired with `frames`; the per-frame `detections` list produced by a pose-tracking component with `return_detections: true` and `return_keypoints: true` (COCO 17 layout).")
    timestamps: Optional[Union[float, List[float], str]] = Field(default=None, description="Per-frame timestamps in seconds paired with `frames`; overrides `frame_rate` when set.")
    frame_rate: Optional[Union[float, str]] = Field(default=None, description="Frames per second; required when `timestamps` is unset.")
    params: GVHMRHumanMeshRecoveryParamsConfig = Field(default_factory=GVHMRHumanMeshRecoveryParamsConfig, description="GVHMR recovery parameters.")

    @model_validator(mode="after")
    def validate_timestamps_or_frame_rate(self):
        if self.timestamps is None and self.frame_rate is None:
            raise ValueError("Either 'timestamps' or 'frame_rate' must be set.")
        return self
