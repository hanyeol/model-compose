from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonImageToVideoModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.IMAGE_TO_VIDEO]
