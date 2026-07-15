from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonVoiceActivityDetectionModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.VOICE_ACTIVITY_DETECTION]
