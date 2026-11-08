from mindor.dsl.schema.component import ModelComponentConfig, ImageBackgroundRemovalModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.IMAGE_BACKGROUND_REMOVAL, ModelDriverType.CUSTOM)
class CustomImageBackgroundRemovalTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == ImageBackgroundRemovalModelFamily.BIREFNET:
            from .birefnet import BiRefNetImageBackgroundRemovalTaskDriver
            return BiRefNetImageBackgroundRemovalTaskDriver(id, config, daemon)

        if config.family == ImageBackgroundRemovalModelFamily.BEN2:
            from .ben2 import Ben2ImageBackgroundRemovalTaskDriver
            return Ben2ImageBackgroundRemovalTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
