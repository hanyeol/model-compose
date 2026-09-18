from mindor.dsl.schema.component import ModelComponentConfig, TextGenerationModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.TEXT_GENERATION, ModelDriverType.CUSTOM)
class CustomTextGenerationTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        raise ValueError(f"Unknown family: {config.family}")
