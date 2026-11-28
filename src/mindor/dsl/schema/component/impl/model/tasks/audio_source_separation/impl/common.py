from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonAudioSourceSeparationModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.AUDIO_SOURCE_SEPARATION]
