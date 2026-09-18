from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import TextClassificationModelActionConfig
from ..common import CommonTextClassificationModelComponentConfig
from .common import TextClassificationModelFamily
from ....common import ModelDriverType

class CustomTextClassificationModelComponentConfig(CommonTextClassificationModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: TextClassificationModelFamily = Field(..., description="Model family selecting the custom text classification implementation.")
    actions: List[TextClassificationModelActionConfig] = Field(default_factory=list, description="Actions this text classification component exposes to workflows.")
