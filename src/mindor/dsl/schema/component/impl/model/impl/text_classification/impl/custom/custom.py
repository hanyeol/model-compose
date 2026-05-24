from typing import Literal, List
from enum import Enum
from pydantic import Field
from mindor.dsl.schema.action import TextClassificationModelActionConfig
from ..common import CommonTextClassificationModelComponentConfig
from ....common import ModelDriver

class CustomTextClassificationModelFamily(str, Enum):
    pass

class CustomTextClassificationModelComponentConfig(CommonTextClassificationModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: CustomTextClassificationModelFamily = Field(..., description="Model family.")
    actions: List[TextClassificationModelActionConfig] = Field(default_factory=list)
