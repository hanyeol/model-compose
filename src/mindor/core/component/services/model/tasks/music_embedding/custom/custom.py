from mindor.dsl.schema.component import ModelComponentConfig, MusicEmbeddingModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.MUSIC_EMBEDDING, ModelDriverType.CUSTOM)
class CustomMusicEmbeddingTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == MusicEmbeddingModelFamily.SAMPLEID:
            from .sampleid import SampleidMusicEmbeddingTaskDriver
            return SampleidMusicEmbeddingTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
