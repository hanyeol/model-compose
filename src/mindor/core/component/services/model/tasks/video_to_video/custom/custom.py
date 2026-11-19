from mindor.dsl.schema.component import ModelComponentConfig, VideoToVideoModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.VIDEO_TO_VIDEO, ModelDriverType.CUSTOM)
class CustomVideoToVideoTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == VideoToVideoModelFamily.WAN:
            from .wan import WanVideoToVideoTaskDriver
            return WanVideoToVideoTaskDriver(id, config, daemon)

        if config.family == VideoToVideoModelFamily.MINIMAX_H3:
            from .minimax_h3.minimax_h3 import MinimaxH3VideoToVideoTaskDriver
            return MinimaxH3VideoToVideoTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
