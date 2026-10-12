from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonImageEdgeDetectionModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.IMAGE_EDGE_DETECTION]
