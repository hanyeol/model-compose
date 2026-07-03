from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonMusicGenerationModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.MUSIC_GENERATION]
