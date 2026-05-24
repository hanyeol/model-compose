from mindor.dsl.schema.component import ModelComponentConfig, CustomFaceEmbeddingModelFamily
from ....base import ModelTaskType, ModelDriver, register_model_task_service

@register_model_task_service(ModelTaskType.FACE_EMBEDDING, ModelDriver.CUSTOM)
class CustomFaceEmbeddingTaskService:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == CustomFaceEmbeddingModelFamily.INSIGHTFACE:
            from .insightface import InsightfaceFaceEmbeddingTaskService
            return InsightfaceFaceEmbeddingTaskService(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
