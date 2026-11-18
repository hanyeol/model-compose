from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import OpenCvVideoGradualSceneDetectorActionConfig
from .common import CommonVideoGradualSceneDetectorComponentConfig, VideoGradualSceneDetectorDriverType

class OpenCvVideoGradualSceneDetectorComponentConfig(CommonVideoGradualSceneDetectorComponentConfig):
    driver: Literal[VideoGradualSceneDetectorDriverType.OPENCV]
    actions: List[OpenCvVideoGradualSceneDetectorActionConfig] = Field(default_factory=list)
