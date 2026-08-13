from mindor.dsl.schema.component import ModelComponentConfig, PoseTrackingModelFamily
from ....base import ModelTaskType, ModelDriver, register_model_task_service

@register_model_task_service(ModelTaskType.POSE_TRACKING, ModelDriver.CUSTOM)
class CustomPoseTrackingTaskService:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == PoseTrackingModelFamily.YOLO:
            from .yolo import YoloPoseTrackingTaskService
            return YoloPoseTrackingTaskService(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
