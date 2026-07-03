from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import TextToTextModelActionConfig
from ..common import CommonTextToTextModelComponentConfig
from .impl.common import TextToTextModelFamily
from ....common import ModelDriver

class CustomTextToTextModelComponentConfig(CommonTextToTextModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: TextToTextModelFamily = Field(..., description="Model family.")
    actions: List[TextToTextModelActionConfig] = Field(default_factory=list)
