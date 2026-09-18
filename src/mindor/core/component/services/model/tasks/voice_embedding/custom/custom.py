from mindor.dsl.schema.component import ModelComponentConfig, VoiceEmbeddingModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.VOICE_EMBEDDING, ModelDriverType.CUSTOM)
class CustomVoiceEmbeddingTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == VoiceEmbeddingModelFamily.PYANNOTE:
            from .pyannote import PyannoteVoiceEmbeddingTaskDriver
            return PyannoteVoiceEmbeddingTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
