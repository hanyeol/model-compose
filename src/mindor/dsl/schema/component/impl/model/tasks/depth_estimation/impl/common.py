from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonDepthEstimationModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.DEPTH_ESTIMATION]
