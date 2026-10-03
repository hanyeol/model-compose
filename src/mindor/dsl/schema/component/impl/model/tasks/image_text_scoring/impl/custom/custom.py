from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import ImageTextScoringModelActionConfig
from ..common import CommonImageTextScoringModelComponentConfig
from .common import ImageTextScoringModelFamily
from ....common import ModelDriverType

class CustomImageTextScoringModelComponentConfig(CommonImageTextScoringModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: ImageTextScoringModelFamily = Field(..., description="Model family selecting the custom image-text scoring implementation.")
    actions: List[ImageTextScoringModelActionConfig] = Field(default_factory=list, description="Actions this image-text scoring component exposes to workflows.")
