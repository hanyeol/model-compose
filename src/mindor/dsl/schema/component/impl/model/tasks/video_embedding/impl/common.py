from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonVideoEmbeddingModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.VIDEO_EMBEDDING]
