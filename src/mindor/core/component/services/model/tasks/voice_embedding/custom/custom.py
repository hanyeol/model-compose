from mindor.dsl.schema.component import ModelComponentConfig, VoiceEmbeddingModelFamily
from ....base import ModelTaskType, ModelDriver, register_model_task_service

@register_model_task_service(ModelTaskType.VOICE_EMBEDDING, ModelDriver.CUSTOM)
class CustomVoiceEmbeddingTaskService:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == VoiceEmbeddingModelFamily.PYANNOTE:
            from .pyannote import PyannoteVoiceEmbeddingTaskService
            return PyannoteVoiceEmbeddingTaskService(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
