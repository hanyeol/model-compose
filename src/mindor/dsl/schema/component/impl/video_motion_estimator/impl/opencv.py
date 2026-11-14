from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import OpenCvVideoMotionEstimatorActionConfig
from .common import CommonVideoMotionEstimatorComponentConfig, VideoMotionEstimatorDriverType

class OpenCvVideoMotionEstimatorComponentConfig(CommonVideoMotionEstimatorComponentConfig):
    driver: Literal[VideoMotionEstimatorDriverType.OPENCV]
    actions: List[OpenCvVideoMotionEstimatorActionConfig] = Field(default_factory=list)
