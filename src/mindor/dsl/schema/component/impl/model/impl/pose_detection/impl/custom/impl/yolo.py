from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import YoloPoseDetectionModelActionConfig
from ...common import CommonPoseDetectionModelComponentConfig
from .common import PoseDetectionModelFamily
from .....common import ModelDriver

class YoloPoseDetectionModelComponentConfig(CommonPoseDetectionModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[PoseDetectionModelFamily.YOLO]
    actions: List[YoloPoseDetectionModelActionConfig] = Field(default_factory=list)
