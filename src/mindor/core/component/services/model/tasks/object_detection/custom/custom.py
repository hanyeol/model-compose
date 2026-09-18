from mindor.dsl.schema.component import ModelComponentConfig, ObjectDetectionModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.OBJECT_DETECTION, ModelDriverType.CUSTOM)
class CustomObjectDetectionTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == ObjectDetectionModelFamily.YOLO:
            from .yolo import YoloObjectDetectionTaskDriver
            return YoloObjectDetectionTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
