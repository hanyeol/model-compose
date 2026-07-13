from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonImageBackgroundRemovalModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.IMAGE_BACKGROUND_REMOVAL]
