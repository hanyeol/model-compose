from mindor.dsl.schema.component import ModelComponentConfig, ImageToVideoModelFamily
from ....base import ModelTaskType, ModelDriver, register_model_task_service

@register_model_task_service(ModelTaskType.IMAGE_TO_VIDEO, ModelDriver.CUSTOM)
class CustomImageToVideoTaskService:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == ImageToVideoModelFamily.WAN:
            from .wan import WanImageToVideoTaskService
            return WanImageToVideoTaskService(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
