from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonTextToVideoModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.TEXT_TO_VIDEO]
