from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import BlazePosePoseDetectionModelActionConfig
from ...common import CommonPoseDetectionModelComponentConfig
from .common import PoseDetectionModelFamily
from .....common import ModelDriver

class BlazePosePoseDetectionModelComponentConfig(CommonPoseDetectionModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[PoseDetectionModelFamily.BLAZEPOSE]
    actions: List[BlazePosePoseDetectionModelActionConfig] = Field(default_factory=list)
