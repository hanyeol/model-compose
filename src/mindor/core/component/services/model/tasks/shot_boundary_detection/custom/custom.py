from mindor.dsl.schema.component import ModelComponentConfig, ShotBoundaryDetectionModelFamily
from ....base import ModelTaskType, ModelDriver, register_model_task_service

@register_model_task_service(ModelTaskType.SHOT_BOUNDARY_DETECTION, ModelDriver.CUSTOM)
class CustomShotBoundaryDetectionTaskService:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == ShotBoundaryDetectionModelFamily.TRANSNETV2:
            from .transnetv2 import TransNetV2ShotBoundaryDetectionTaskService
            return TransNetV2ShotBoundaryDetectionTaskService(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
