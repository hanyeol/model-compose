from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonTextToSpeechModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.TEXT_TO_SPEECH]
