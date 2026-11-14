from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class VideoMotionEstimatorDriverType(str, Enum):
    OPENCV = "opencv"

class CommonVideoMotionEstimatorComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.VIDEO_MOTION_ESTIMATOR]
    driver: VideoMotionEstimatorDriverType = Field(..., description="Backend implementation used for motion estimation.")
