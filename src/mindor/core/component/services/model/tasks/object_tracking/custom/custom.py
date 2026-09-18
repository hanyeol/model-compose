from mindor.dsl.schema.component import ModelComponentConfig, ObjectTrackingModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.OBJECT_TRACKING, ModelDriverType.CUSTOM)
class CustomObjectTrackingTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == ObjectTrackingModelFamily.YOLO:
            from .yolo import YoloObjectTrackingTaskDriver
            return YoloObjectTrackingTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
