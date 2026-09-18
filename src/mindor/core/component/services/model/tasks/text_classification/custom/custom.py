from mindor.dsl.schema.component import ModelComponentConfig, TextClassificationModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.TEXT_CLASSIFICATION, ModelDriverType.CUSTOM)
class CustomTextClassificationTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        raise ValueError(f"Unknown family: {config.family}")
