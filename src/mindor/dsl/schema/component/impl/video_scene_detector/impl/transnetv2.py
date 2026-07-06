from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import VideoSceneDetectorActionConfig
from .common import CommonVideoSceneDetectorComponentConfig, VideoSceneDetectorDriver

class Transnetv2VideoSceneDetectorComponentConfig(CommonVideoSceneDetectorComponentConfig):
    driver: Literal[VideoSceneDetectorDriver.TRANSNETV2]
    actions: List[VideoSceneDetectorActionConfig] = Field(default_factory=list)
