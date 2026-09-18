from mindor.dsl.schema.component import ModelComponentConfig, PoseTrackingModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.POSE_TRACKING, ModelDriverType.CUSTOM)
class CustomPoseTrackingTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == PoseTrackingModelFamily.YOLO:
            from .yolo import YoloPoseTrackingTaskDriver
            return YoloPoseTrackingTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
