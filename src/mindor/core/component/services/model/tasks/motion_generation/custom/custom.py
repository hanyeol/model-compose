from mindor.dsl.schema.component import ModelComponentConfig, MotionGenerationModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.MOTION_GENERATION, ModelDriverType.CUSTOM)
class CustomMotionGenerationTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == MotionGenerationModelFamily.KIMODO:
            from .kimodo import KimodoMotionGenerationTaskDriver
            return KimodoMotionGenerationTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
