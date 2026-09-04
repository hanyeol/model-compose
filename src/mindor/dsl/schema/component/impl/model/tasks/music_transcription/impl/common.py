from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonMusicTranscriptionModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.MUSIC_TRANSCRIPTION]
