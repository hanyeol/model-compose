from typing import Literal
from ...common import LanguageModelComponentConfig, ModelTaskType

class CommonTextEmbeddingModelComponentConfig(LanguageModelComponentConfig):
    task: Literal[ModelTaskType.TEXT_EMBEDDING]
