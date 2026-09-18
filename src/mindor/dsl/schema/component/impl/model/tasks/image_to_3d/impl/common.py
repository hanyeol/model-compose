from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonImageTo3DModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.IMAGE_TO_3D]
