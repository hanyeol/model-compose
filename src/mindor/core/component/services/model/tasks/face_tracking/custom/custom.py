from mindor.dsl.schema.component import ModelComponentConfig, FaceTrackingModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.FACE_TRACKING, ModelDriverType.CUSTOM)
class CustomFaceTrackingTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == FaceTrackingModelFamily.INSIGHTFACE:
            from .insightface import InsightfaceFaceTrackingTaskDriver
            return InsightfaceFaceTrackingTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
