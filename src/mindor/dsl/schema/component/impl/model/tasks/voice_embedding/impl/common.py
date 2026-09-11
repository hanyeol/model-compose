from typing import Literal
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonVoiceEmbeddingModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.VOICE_EMBEDDING]
