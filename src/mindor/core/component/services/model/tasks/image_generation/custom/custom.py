from mindor.dsl.schema.component import ModelComponentConfig
from ....base import ModelTaskType, ModelDriver, register_model_task_service

@register_model_task_service(ModelTaskType.IMAGE_GENERATION, ModelDriver.CUSTOM)
class CustomImageGenerationTaskService:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        raise ValueError(f"Unknown family: {config.family}")
