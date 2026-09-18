from mindor.dsl.schema.component import ModelComponentConfig, ImageTextToTextModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.IMAGE_TEXT_TO_TEXT, ModelDriverType.CUSTOM)
class CustomImageTextToTextTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        raise ValueError(f"Unknown family: {config.family}")
