from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, TypeAlias, Any
from mindor.dsl.schema.component import ModelComponentConfig, ImageGenerationModelFamily
from ...base import ModelTaskType, ModelDriver, register_model_task_service

@register_model_task_service(ModelTaskType.IMAGE_GENERATION, ModelDriver.CUSTOM)
class CustomImageGenerationTaskService:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        if config.family == ImageGenerationModelFamily.HUNYUAN_IMAGE:
            from .hunyuan_image import HunyuanImageGenerationTaskService
            return HunyuanImageGenerationTaskService(id, config, daemon)

        raise ValueError(f"Unknown architecture: {config.architecture}")
