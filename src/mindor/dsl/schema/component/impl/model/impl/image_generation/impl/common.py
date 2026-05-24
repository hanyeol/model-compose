from typing import Literal, Optional
from pydantic import Field
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonImageGenerationModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.IMAGE_GENERATION]
    version: Optional[str] = Field(default=None, description="Model version or variant.")
