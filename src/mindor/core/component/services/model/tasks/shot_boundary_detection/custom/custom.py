from mindor.dsl.schema.component import ModelComponentConfig, ShotBoundaryDetectionModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.SHOT_BOUNDARY_DETECTION, ModelDriverType.CUSTOM)
class CustomShotBoundaryDetectionTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == ShotBoundaryDetectionModelFamily.TRANSNETV2:
            from .transnetv2 import TransNetV2ShotBoundaryDetectionTaskDriver
            return TransNetV2ShotBoundaryDetectionTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
