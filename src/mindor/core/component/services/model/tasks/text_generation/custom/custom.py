from mindor.dsl.schema.component import ModelComponentConfig, CustomTextGenerationModelFamily
from ....base import ModelTaskType, ModelDriver, register_model_task_service

@register_model_task_service(ModelTaskType.TEXT_GENERATION, ModelDriver.CUSTOM)
class CustomTextGenerationTaskService:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        raise ValueError(f"Unknown family: {config.family}")
