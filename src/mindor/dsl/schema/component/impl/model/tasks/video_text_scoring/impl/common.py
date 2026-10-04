from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonVideoTextScoringModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.VIDEO_TEXT_SCORING]
