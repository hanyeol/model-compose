from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import FFplayVideoPlaybackActionConfig
from .common import CommonVideoPlaybackComponentConfig, VideoPlaybackDriverType

class FFplayVideoPlaybackComponentConfig(CommonVideoPlaybackComponentConfig):
    driver: Literal[VideoPlaybackDriverType.FFPLAY]
    actions: List[FFplayVideoPlaybackActionConfig] = Field(default_factory=list)
