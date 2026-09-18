from mindor.dsl.schema.component import ModelComponentConfig, FaceEmbeddingModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.FACE_EMBEDDING, ModelDriverType.CUSTOM)
class CustomFaceEmbeddingTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == FaceEmbeddingModelFamily.INSIGHTFACE:
            from .insightface import InsightfaceFaceEmbeddingTaskDriver
            return InsightfaceFaceEmbeddingTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
