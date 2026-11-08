from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import BiRefNetImageBackgroundRemovalModelActionConfig
from ..common import CommonImageBackgroundRemovalModelComponentConfig
from .common import ImageBackgroundRemovalModelFamily
from ....common import ModelDriverType

class BiRefNetImageBackgroundRemovalModelComponentConfig(CommonImageBackgroundRemovalModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[ImageBackgroundRemovalModelFamily.BIREFNET]
    actions: List[BiRefNetImageBackgroundRemovalModelActionConfig] = Field(default_factory=list, description="Actions this image background removal component exposes to workflows.")
