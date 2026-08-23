from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import VideoPlaybackActionConfig
from .common import CommonVideoPlaybackComponentConfig, VideoPlaybackDriver

class FFplayVideoPlaybackComponentConfig(CommonVideoPlaybackComponentConfig):
    driver: Literal[VideoPlaybackDriver.FFPLAY]
    actions: List[VideoPlaybackActionConfig] = Field(default_factory=list)
