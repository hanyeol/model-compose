from mindor.dsl.schema.component import ModelComponentConfig, ObjectDetectionModelFamily
from ....base import ModelTaskType, ModelDriver, register_model_task_service

@register_model_task_service(ModelTaskType.OBJECT_DETECTION, ModelDriver.CUSTOM)
class CustomObjectDetectionTaskService:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == ObjectDetectionModelFamily.YOLO:
            from .yolo import YoloObjectDetectionTaskService
            return YoloObjectDetectionTaskService(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
