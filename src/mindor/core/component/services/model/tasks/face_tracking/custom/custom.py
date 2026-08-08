from mindor.dsl.schema.component import ModelComponentConfig, FaceTrackingModelFamily
from ....base import ModelTaskType, ModelDriver, register_model_task_service

@register_model_task_service(ModelTaskType.FACE_TRACKING, ModelDriver.CUSTOM)
class CustomFaceTrackingTaskService:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == FaceTrackingModelFamily.INSIGHTFACE:
            from .insightface import InsightfaceFaceTrackingTaskService
            return InsightfaceFaceTrackingTaskService(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
