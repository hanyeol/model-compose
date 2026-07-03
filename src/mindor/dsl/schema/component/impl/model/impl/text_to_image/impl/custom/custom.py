from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import TextToImageModelActionConfig
from ..common import CommonTextToImageModelComponentConfig
from .impl.common import TextToImageModelFamily
from ....common import ModelDriver

class CustomTextToImageModelComponentConfig(CommonTextToImageModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: TextToImageModelFamily = Field(..., description="Model family.")
    actions: List[TextToImageModelActionConfig] = Field(default_factory=list)
