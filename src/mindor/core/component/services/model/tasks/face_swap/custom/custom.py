from mindor.dsl.schema.component import ModelComponentConfig, FaceSwapModelFamily
from ....base import ModelTaskType, ModelDriver, register_model_task_service

@register_model_task_service(ModelTaskType.FACE_SWAP, ModelDriver.CUSTOM)
class CustomFaceSwapTaskService:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == FaceSwapModelFamily.INSIGHTFACE:
            from .insightface import InsightfaceFaceSwapTaskService
            return InsightfaceFaceSwapTaskService(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
