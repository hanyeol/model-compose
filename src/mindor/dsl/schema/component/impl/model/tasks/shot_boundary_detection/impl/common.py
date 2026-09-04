from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonShotBoundaryDetectionModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.SHOT_BOUNDARY_DETECTION]
