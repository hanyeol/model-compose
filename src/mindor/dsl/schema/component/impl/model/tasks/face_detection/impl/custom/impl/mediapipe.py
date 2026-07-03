from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import BlazeFaceFaceDetectionModelActionConfig
from ...common import CommonFaceDetectionModelComponentConfig
from .common import FaceDetectionModelFamily
from .....common import ModelDriver

class BlazeFaceFaceDetectionModelComponentConfig(CommonFaceDetectionModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[FaceDetectionModelFamily.BLAZEFACE]
    actions: List[BlazeFaceFaceDetectionModelActionConfig] = Field(default_factory=list)
