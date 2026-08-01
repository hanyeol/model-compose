from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonAudioTextAlignmentModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.AUDIO_TEXT_ALIGNMENT]
