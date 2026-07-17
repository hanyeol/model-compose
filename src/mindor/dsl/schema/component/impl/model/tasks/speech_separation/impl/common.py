from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonSpeechSeparationModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.SPEECH_SEPARATION]
