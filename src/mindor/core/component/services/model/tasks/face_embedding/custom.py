from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, TypeAlias, Any
from mindor.dsl.schema.component import ModelComponentConfig, FaceEmbeddingModelFamily
from ...base import ModelTaskType, ModelDriver, register_model_task_service

@register_model_task_service(ModelTaskType.FACE_EMBEDDING, ModelDriver.CUSTOM)
class CustomFaceEmbeddingTaskService:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == FaceEmbeddingModelFamily.INSIGHTFACE:
            from .insightface import InsightfaceFaceEmbeddingTaskService
            return InsightfaceFaceEmbeddingTaskService(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
