from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonVideoToVideoModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.VIDEO_TO_VIDEO]
