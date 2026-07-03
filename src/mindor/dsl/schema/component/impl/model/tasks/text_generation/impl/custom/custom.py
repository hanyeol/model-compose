from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import TextGenerationModelActionConfig
from ..common import CommonTextGenerationModelComponentConfig
from .impl.common import TextGenerationModelFamily
from ....common import ModelDriver

class CustomTextGenerationModelComponentConfig(CommonTextGenerationModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: TextGenerationModelFamily = Field(..., description="Model family.")
    actions: List[TextGenerationModelActionConfig] = Field(default_factory=list)
