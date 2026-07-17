from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonSpeakerDiarizationModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.SPEAKER_DIARIZATION]
