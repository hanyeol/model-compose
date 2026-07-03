from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonImageUpscaleModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.IMAGE_UPSCALE]
