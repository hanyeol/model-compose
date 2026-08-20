from mindor.dsl.schema.component import ModelComponentConfig, TextToVideoModelFamily
from ....base import ModelTaskType, ModelDriver, register_model_task_service

@register_model_task_service(ModelTaskType.TEXT_TO_VIDEO, ModelDriver.CUSTOM)
class CustomTextToVideoTaskService:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == TextToVideoModelFamily.WAN:
            from .wan import WanTextToVideoTaskService
            return WanTextToVideoTaskService(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
