from typing import Union
from pydantic import Field
from .common import CommonCameraPoseEstimatorActionConfig

class ColmapCameraPoseEstimatorActionConfig(CommonCameraPoseEstimatorActionConfig):
    return_cameras: Union[bool, str] = Field(default=True, description="Include recovered camera intrinsics as a list of dicts in the result.")
    return_poses: Union[bool, str] = Field(default=True, description="Include per-image world-from-camera poses as a list of dicts in the result.")
    return_points: Union[bool, str] = Field(default=False, description="Include the sparse point cloud (with camera frustums) as a GLB model in the result.")
    return_metadata: Union[bool, str] = Field(default=True, description="Include reconstruction summary in the result.")
