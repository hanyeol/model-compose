from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonSpeechToTextModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.SPEECH_TO_TEXT]
