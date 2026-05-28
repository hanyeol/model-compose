from mindor.dsl.schema.component import ModelComponentConfig, TextClassificationModelFamily
from ....base import ModelTaskType, ModelDriver, register_model_task_service

@register_model_task_service(ModelTaskType.TEXT_CLASSIFICATION, ModelDriver.CUSTOM)
class CustomTextClassificationTaskService:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        raise ValueError(f"Unknown family: {config.family}")
