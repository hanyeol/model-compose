from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import TextToTextModelActionConfig
from ..common import CommonTextToTextModelComponentConfig
from .common import TextToTextModelFamily
from ....common import ModelDriverType

class CustomTextToTextModelComponentConfig(CommonTextToTextModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: TextToTextModelFamily = Field(..., description="Model family selecting the custom text-to-text implementation.")
    actions: List[TextToTextModelActionConfig] = Field(default_factory=list, description="Actions this text-to-text component exposes to workflows.")
