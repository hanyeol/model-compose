from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import SamImageSegmentationModelActionConfig
from ...common import CommonImageSegmentationModelComponentConfig
from .common import ImageSegmentationModelFamily
from .....common import ModelDriver

class SamImageSegmentationModelComponentConfig(CommonImageSegmentationModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[ImageSegmentationModelFamily.SAM]
    actions: List[SamImageSegmentationModelActionConfig] = Field(default_factory=list)
