from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonImageToTextModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.IMAGE_TO_TEXT]
