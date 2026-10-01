from mindor.dsl.schema.component import ModelComponentConfig, TextToVideoModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.TEXT_TO_VIDEO, ModelDriverType.CUSTOM)
class CustomTextToVideoTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == TextToVideoModelFamily.WAN:
            from .wan import WanTextToVideoTaskDriver
            return WanTextToVideoTaskDriver(id, config, daemon)

        if config.family == TextToVideoModelFamily.MINIMAX_H3:
            from .minimax_h3.minimax_h3 import MinimaxH3TextToVideoTaskDriver
            return MinimaxH3TextToVideoTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
