from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class CameraPoseEstimatorDriverType(str, Enum):
    COLMAP = "colmap"

class CommonCameraPoseEstimatorComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.CAMERA_POSE_ESTIMATOR]
    driver: CameraPoseEstimatorDriverType = Field(..., description="Backend implementation used for camera pose estimation.")
