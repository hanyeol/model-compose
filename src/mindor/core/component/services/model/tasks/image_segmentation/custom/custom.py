from mindor.dsl.schema.component import ModelComponentConfig, ImageSegmentationModelFamily
from ....base import ModelTaskType, ModelDriverType, register_model_task_driver

@register_model_task_driver(ModelTaskType.IMAGE_SEGMENTATION, ModelDriverType.CUSTOM)
class CustomImageSegmentationTaskDriver:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == ImageSegmentationModelFamily.SAM:
            from .sam import SamImageSegmentationTaskDriver
            return SamImageSegmentationTaskDriver(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
