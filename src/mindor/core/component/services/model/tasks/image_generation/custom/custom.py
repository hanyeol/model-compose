from mindor.dsl.schema.component import ModelComponentConfig, ImageGenerationModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.IMAGE_GENERATION, ModelDriverType.CUSTOM)
class CustomImageGenerationTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == ImageGenerationModelFamily.MINIMAX_H3:
            from .minimax_h3.minimax_h3 import MinimaxH3ImageGenerationTaskDriver
            return MinimaxH3ImageGenerationTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
