from mindor.dsl.schema.component import ModelComponentConfig, ImageEmbeddingModelFamily
from ....base import ModelTaskType, ModelDriver, register_model_task_service

@register_model_task_service(ModelTaskType.IMAGE_EMBEDDING, ModelDriver.CUSTOM)
class CustomImageEmbeddingTaskService:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        raise ValueError(f"Unknown family: {config.family}")
