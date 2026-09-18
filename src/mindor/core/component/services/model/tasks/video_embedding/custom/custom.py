from mindor.dsl.schema.component import ModelComponentConfig, VideoEmbeddingModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.VIDEO_EMBEDDING, ModelDriverType.CUSTOM)
class CustomVideoEmbeddingTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        raise ValueError(f"Unknown family: {config.family}")
