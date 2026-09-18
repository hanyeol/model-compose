from mindor.dsl.schema.component import ModelComponentConfig, ImageToVideoModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.IMAGE_TO_VIDEO, ModelDriverType.CUSTOM)
class CustomImageToVideoTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == ImageToVideoModelFamily.WAN:
            from .wan import WanImageToVideoTaskDriver
            return WanImageToVideoTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
