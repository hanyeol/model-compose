from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonMusicSourceSeparationModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.MUSIC_SOURCE_SEPARATION]
