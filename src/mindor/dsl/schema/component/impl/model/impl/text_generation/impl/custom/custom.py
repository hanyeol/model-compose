from typing import Literal, List
from enum import Enum
from pydantic import Field
from mindor.dsl.schema.action import TextGenerationModelActionConfig
from ..common import CommonTextGenerationModelComponentConfig
from ....common import ModelDriver

class CustomTextGenerationModelFamily(str, Enum):
    pass

class CustomTextGenerationModelComponentConfig(CommonTextGenerationModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: CustomTextGenerationModelFamily = Field(..., description="Model family.")
    actions: List[TextGenerationModelActionConfig] = Field(default_factory=list)
