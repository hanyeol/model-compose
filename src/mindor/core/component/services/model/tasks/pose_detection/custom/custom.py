from mindor.dsl.schema.component import ModelComponentConfig, PoseDetectionModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.POSE_DETECTION, ModelDriverType.CUSTOM)
class CustomPoseDetectionTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == PoseDetectionModelFamily.BLAZEPOSE:
            from .mediapipe import BlazePosePoseDetectionTaskDriver
            return BlazePosePoseDetectionTaskDriver(id, config, daemon)

        if config.family == PoseDetectionModelFamily.YOLO:
            from .yolo import YoloPoseDetectionTaskDriver
            return YoloPoseDetectionTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
