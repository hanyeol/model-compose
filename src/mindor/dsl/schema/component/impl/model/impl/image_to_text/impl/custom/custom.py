from typing import Literal, List
from enum import Enum
from pydantic import Field
from mindor.dsl.schema.action import ImageToTextModelActionConfig
from ..common import CommonImageToTextModelComponentConfig
from ....common import ModelDriver

class CustomImageToTextModelFamily(str, Enum):
    pass

class CustomImageToTextModelComponentConfig(CommonImageToTextModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: CustomImageToTextModelFamily = Field(..., description="Model family.")
    actions: List[ImageToTextModelActionConfig] = Field(default_factory=list)
