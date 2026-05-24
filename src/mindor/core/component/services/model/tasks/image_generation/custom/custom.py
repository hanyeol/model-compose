from mindor.dsl.schema.component import ModelComponentConfig, CustomImageGenerationModelFamily
from ....base import ModelTaskType, ModelDriver, register_model_task_service

@register_model_task_service(ModelTaskType.IMAGE_GENERATION, ModelDriver.CUSTOM)
class CustomImageGenerationTaskService:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == CustomImageGenerationModelFamily.HUNYUAN_IMAGE:
            from .hunyuan_image import HunyuanImageGenerationTaskService
            return HunyuanImageGenerationTaskService(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
