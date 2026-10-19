from mindor.dsl.schema.component import ModelComponentConfig, FaceEmotionClassificationModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.FACE_EMOTION_CLASSIFICATION, ModelDriverType.CUSTOM)
class CustomFaceEmotionClassificationTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == FaceEmotionClassificationModelFamily.HSEMOTION:
            from .hsemotion import HSEmotionFaceEmotionClassificationTaskDriver
            return HSEmotionFaceEmotionClassificationTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
