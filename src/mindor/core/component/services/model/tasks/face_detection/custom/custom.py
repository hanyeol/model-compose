from mindor.dsl.schema.component import ModelComponentConfig, FaceDetectionModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.FACE_DETECTION, ModelDriverType.CUSTOM)
class CustomFaceDetectionTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == FaceDetectionModelFamily.BLAZEFACE:
            from .mediapipe import BlazeFaceFaceDetectionTaskDriver
            return BlazeFaceFaceDetectionTaskDriver(id, config, daemon)

        if config.family == FaceDetectionModelFamily.INSIGHTFACE:
            from .insightface import InsightfaceFaceDetectionTaskDriver
            return InsightfaceFaceDetectionTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
