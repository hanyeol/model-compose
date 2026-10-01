from mindor.dsl.schema.component import ModelComponentConfig, ImageToTextModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.IMAGE_TO_TEXT, ModelDriverType.CUSTOM)
class CustomImageToTextTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == ImageToTextModelFamily.RAPIDOCR:
            from .rapidocr import RapidOcrImageToTextTaskDriver
            return RapidOcrImageToTextTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
