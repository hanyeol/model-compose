from mindor.dsl.schema.component import ModelComponentConfig, FaceDetectionModelFamily
from ....base import ModelTaskType, ModelDriver, register_model_task_service

@register_model_task_service(ModelTaskType.FACE_DETECTION, ModelDriver.CUSTOM)
class CustomFaceDetectionTaskService:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == FaceDetectionModelFamily.BLAZEFACE:
            from .mediapipe import BlazeFaceFaceDetectionTaskService
            return BlazeFaceFaceDetectionTaskService(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
