from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonPoseDetectionModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.POSE_DETECTION]
