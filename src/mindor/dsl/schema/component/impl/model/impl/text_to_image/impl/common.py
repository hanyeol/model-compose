from typing import Literal, Optional
from pydantic import Field
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonTextToImageModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.TEXT_TO_IMAGE]
    version: Optional[str] = Field(default=None, description="Model version or variant.")
