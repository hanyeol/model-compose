from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonImageUpscalingModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.IMAGE_UPSCALING]
