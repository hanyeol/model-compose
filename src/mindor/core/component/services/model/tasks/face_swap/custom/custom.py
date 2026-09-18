from mindor.dsl.schema.component import ModelComponentConfig, FaceSwapModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.FACE_SWAP, ModelDriverType.CUSTOM)
class CustomFaceSwapTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == FaceSwapModelFamily.INSIGHTFACE:
            from .insightface import InsightfaceFaceSwapTaskDriver

            return InsightfaceFaceSwapTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
