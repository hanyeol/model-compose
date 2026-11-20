from mindor.dsl.schema.component import ModelComponentConfig, HandDetectionModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.HAND_DETECTION, ModelDriverType.CUSTOM)
class CustomHandDetectionTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == HandDetectionModelFamily.BLAZEHAND:
            from .mediapipe import BlazeHandHandDetectionTaskDriver
            return BlazeHandHandDetectionTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
