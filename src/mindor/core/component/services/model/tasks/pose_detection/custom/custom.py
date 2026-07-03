from mindor.dsl.schema.component import ModelComponentConfig, PoseDetectionModelFamily
from ....base import ModelTaskType, ModelDriver, register_model_task_service

@register_model_task_service(ModelTaskType.POSE_DETECTION, ModelDriver.CUSTOM)
class CustomPoseDetectionTaskService:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == PoseDetectionModelFamily.BLAZEPOSE:
            from .mediapipe import BlazePosePoseDetectionTaskService
            return BlazePosePoseDetectionTaskService(id, config, daemon)

        if config.family == PoseDetectionModelFamily.YOLO:
            from .yolo import YoloPoseDetectionTaskService
            return YoloPoseDetectionTaskService(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
