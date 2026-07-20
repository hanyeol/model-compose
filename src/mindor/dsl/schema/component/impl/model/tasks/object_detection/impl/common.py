from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonObjectDetectionModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.OBJECT_DETECTION]
