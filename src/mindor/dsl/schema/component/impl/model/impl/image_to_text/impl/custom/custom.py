from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import ImageToTextModelActionConfig
from ..common import CommonImageToTextModelComponentConfig
from .impl.common import ImageToTextModelFamily
from ....common import ModelDriver

class CustomImageToTextModelComponentConfig(CommonImageToTextModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: ImageToTextModelFamily = Field(..., description="Model family.")
    actions: List[ImageToTextModelActionConfig] = Field(default_factory=list)
