from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import InsightfaceFaceTrackingModelActionConfig
from ...common import CommonFaceTrackingModelComponentConfig
from .common import FaceTrackingModelFamily
from .....common import ModelDriver

class InsightfaceFaceTrackingModelComponentConfig(CommonFaceTrackingModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[FaceTrackingModelFamily.INSIGHTFACE]
    actions: List[InsightfaceFaceTrackingModelActionConfig] = Field(default_factory=list)
