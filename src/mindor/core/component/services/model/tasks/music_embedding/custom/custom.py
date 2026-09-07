from mindor.dsl.schema.component import ModelComponentConfig, MusicEmbeddingModelFamily
from ....base import ModelTaskType, ModelDriver, register_model_task_service

@register_model_task_service(ModelTaskType.MUSIC_EMBEDDING, ModelDriver.CUSTOM)
class CustomMusicEmbeddingTaskService:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == MusicEmbeddingModelFamily.SAMPLEID:
            from .sampleid import SampleidMusicEmbeddingTaskService
            return SampleidMusicEmbeddingTaskService(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
