from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonMusicEmbeddingModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.MUSIC_EMBEDDING]
