from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import TextClassificationModelActionConfig
from ..common import CommonTextClassificationModelComponentConfig
from .common import TextClassificationModelFamily
from ....common import ModelDriver

class CustomTextClassificationModelComponentConfig(CommonTextClassificationModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: TextClassificationModelFamily = Field(..., description="Model family selecting the custom text classification implementation.")
    actions: List[TextClassificationModelActionConfig] = Field(default_factory=list, description="Actions this text classification component exposes to workflows.")
