from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import Ben2ImageBackgroundRemovalModelActionConfig
from ..common import CommonImageBackgroundRemovalModelComponentConfig
from .common import ImageBackgroundRemovalModelFamily
from ....common import ModelDriverType

class Ben2ImageBackgroundRemovalModelComponentConfig(CommonImageBackgroundRemovalModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[ImageBackgroundRemovalModelFamily.BEN2]
    actions: List[Ben2ImageBackgroundRemovalModelActionConfig] = Field(default_factory=list, description="Actions this image background removal component exposes to workflows.")
