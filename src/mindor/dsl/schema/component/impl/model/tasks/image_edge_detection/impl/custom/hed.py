from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import HedImageEdgeDetectionModelActionConfig
from ..common import CommonImageEdgeDetectionModelComponentConfig
from .common import ImageEdgeDetectionModelFamily
from ....common import ModelDriverType

class HedImageEdgeDetectionModelComponentConfig(CommonImageEdgeDetectionModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[ImageEdgeDetectionModelFamily.HED]
    actions: List[HedImageEdgeDetectionModelActionConfig] = Field(default_factory=list, description="Actions this HED edge detection component exposes to workflows.")
