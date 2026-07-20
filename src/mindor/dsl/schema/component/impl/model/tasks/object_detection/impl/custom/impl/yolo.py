from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import YoloObjectDetectionModelActionConfig
from ...common import CommonObjectDetectionModelComponentConfig
from .common import ObjectDetectionModelFamily
from .....common import ModelDriver

class YoloObjectDetectionModelComponentConfig(CommonObjectDetectionModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[ObjectDetectionModelFamily.YOLO]
    actions: List[YoloObjectDetectionModelActionConfig] = Field(default_factory=list)
