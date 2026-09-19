from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonMusicBeatTrackingModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.MUSIC_BEAT_TRACKING]
