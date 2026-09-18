from mindor.dsl.schema.component import ModelComponentConfig, TextEmbeddingModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.TEXT_EMBEDDING, ModelDriverType.CUSTOM)
class CustomTextEmbeddingTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        raise ValueError(f"Unknown family: {config.family}")
