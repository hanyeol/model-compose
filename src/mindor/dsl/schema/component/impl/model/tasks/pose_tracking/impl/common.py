from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonPoseTrackingModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.POSE_TRACKING]
