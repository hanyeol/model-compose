from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import VideoSceneDetectorActionConfig
from .common import CommonVideoSceneDetectorComponentConfig, VideoSceneDetectorDriver

class PyscenedetectVideoSceneDetectorComponentConfig(CommonVideoSceneDetectorComponentConfig):
    driver: Literal[VideoSceneDetectorDriver.PYSCENEDETECT]
    actions: List[VideoSceneDetectorActionConfig] = Field(default_factory=list)
