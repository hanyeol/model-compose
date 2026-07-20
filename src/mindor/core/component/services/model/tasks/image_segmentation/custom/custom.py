from mindor.dsl.schema.component import ModelComponentConfig, ImageSegmentationModelFamily
from ....base import ModelTaskType, ModelDriver, register_model_task_service

@register_model_task_service(ModelTaskType.IMAGE_SEGMENTATION, ModelDriver.CUSTOM)
class CustomImageSegmentationTaskService:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == ImageSegmentationModelFamily.SAM:
            from .sam import SamImageSegmentationTaskService
            return SamImageSegmentationTaskService(id, config, daemon)

        raise ValueError(f"Unknown family: {config.family}")
