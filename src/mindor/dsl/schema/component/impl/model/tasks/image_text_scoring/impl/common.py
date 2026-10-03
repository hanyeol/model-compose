from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonImageTextScoringModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.IMAGE_TEXT_SCORING]
