from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonHandDetectionModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.HAND_DETECTION]
