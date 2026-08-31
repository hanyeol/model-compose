from mindor.dsl.schema.component import ModelComponentConfig, ObjectTrackingModelFamily
from ....base import ModelTaskType, ModelDriver, register_model_task_service

@register_model_task_service(ModelTaskType.OBJECT_TRACKING, ModelDriver.CUSTOM)
class CustomObjectTrackingTaskService:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == ObjectTrackingModelFamily.YOLO:
            from .yolo import YoloObjectTrackingTaskService
            return YoloObjectTrackingTaskService(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
