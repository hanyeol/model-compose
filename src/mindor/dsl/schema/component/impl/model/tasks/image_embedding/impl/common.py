from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonImageEmbeddingModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.IMAGE_EMBEDDING]
