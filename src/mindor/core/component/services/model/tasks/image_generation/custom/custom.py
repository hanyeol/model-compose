from mindor.dsl.schema.component import ModelComponentConfig
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.IMAGE_GENERATION, ModelDriverType.CUSTOM)
class CustomImageGenerationTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        raise ValueError(f"Unknown family: {config.family}")
