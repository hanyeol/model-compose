from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import PidinetImageEdgeDetectionModelActionConfig
from ..common import CommonImageEdgeDetectionModelComponentConfig
from .common import ImageEdgeDetectionModelFamily
from ....common import ModelDriverType

class PidinetImageEdgeDetectionModelComponentConfig(CommonImageEdgeDetectionModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[ImageEdgeDetectionModelFamily.PIDINET]
    actions: List[PidinetImageEdgeDetectionModelActionConfig] = Field(default_factory=list, description="Actions this PiDiNet edge detection component exposes to workflows.")
