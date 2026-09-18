from mindor.dsl.schema.component import ModelComponentConfig, ImageEmbeddingModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.IMAGE_EMBEDDING, ModelDriverType.CUSTOM)
class CustomImageEmbeddingTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        raise ValueError(f"Unknown family: {config.family}")
