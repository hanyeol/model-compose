from typing import Union
from pydantic import Field
from .common import CommonCameraPoseEstimatorActionConfig

class ColmapCameraPoseEstimatorActionConfig(CommonCameraPoseEstimatorActionConfig):
    return_points: Union[bool, str] = Field(default=False, description="Include the sparse point cloud (with camera frustums) as a GLB model in the result.")
