from mindor.dsl.schema.component import ModelComponentConfig, ImageTextToTextModelFamily
from ....base import ModelTaskType, ModelDriver, register_model_task_service

@register_model_task_service(ModelTaskType.IMAGE_TEXT_TO_TEXT, ModelDriver.CUSTOM)
class CustomImageTextToTextTaskService:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        raise ValueError(f"Unknown family: {config.family}")
