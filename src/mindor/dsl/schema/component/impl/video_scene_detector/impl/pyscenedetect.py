from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import VideoSceneDetectorActionConfig
from .common import CommonVideoSceneDetectorComponentConfig, VideoSceneDetectorDriverType

class PyscenedetectVideoSceneDetectorComponentConfig(CommonVideoSceneDetectorComponentConfig):
    driver: Literal[VideoSceneDetectorDriverType.PYSCENEDETECT]
    actions: List[VideoSceneDetectorActionConfig] = Field(default_factory=list)
