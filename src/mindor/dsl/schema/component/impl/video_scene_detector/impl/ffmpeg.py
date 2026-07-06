from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import VideoSceneDetectorActionConfig
from .common import CommonVideoSceneDetectorComponentConfig, VideoSceneDetectorDriver

class FfmpegVideoSceneDetectorComponentConfig(CommonVideoSceneDetectorComponentConfig):
    driver: Literal[VideoSceneDetectorDriver.FFMPEG]
    actions: List[VideoSceneDetectorActionConfig] = Field(default_factory=list)
