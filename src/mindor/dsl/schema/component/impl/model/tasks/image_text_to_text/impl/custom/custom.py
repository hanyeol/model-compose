from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import ImageTextToTextModelActionConfig
from ..common import CommonImageTextToTextModelComponentConfig
from .common import ImageTextToTextModelFamily
from ....common import ModelDriverType

class CustomImageTextToTextModelComponentConfig(CommonImageTextToTextModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: ImageTextToTextModelFamily = Field(..., description="Model family selecting the custom image-text-to-text implementation.")
    actions: List[ImageTextToTextModelActionConfig] = Field(default_factory=list, description="Actions this image-text-to-text component exposes to workflows.")
