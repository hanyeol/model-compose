from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import ModelComponentConfig, ImageToTextModelFamily
from ...base import ModelTaskType, ModelDriver, register_model_task_service

@register_model_task_service(ModelTaskType.IMAGE_TO_TEXT, ModelDriver.CUSTOM)
class CustomImageToTextTaskService:
    def __new__(cls, id: str, config: ModelComponentConfig, daemon: bool):
        raise ValueError(f"Unknown family: {config.family}")
