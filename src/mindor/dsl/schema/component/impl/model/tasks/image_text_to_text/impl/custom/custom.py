from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import ImageTextToTextModelActionConfig
from ..common import CommonImageTextToTextModelComponentConfig
from .impl.common import ImageTextToTextModelFamily
from ....common import ModelDriver

class CustomImageTextToTextModelComponentConfig(CommonImageTextToTextModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: ImageTextToTextModelFamily = Field(..., description="Model family selecting the custom image-text-to-text implementation.")
    actions: List[ImageTextToTextModelActionConfig] = Field(default_factory=list, description="Actions this image-text-to-text component exposes to workflows.")
