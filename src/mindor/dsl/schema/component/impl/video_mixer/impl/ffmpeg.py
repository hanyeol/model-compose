from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import VideoMixerActionConfig
from .common import CommonVideoMixerComponentConfig, VideoMixerDriver

class FFmpegVideoMixerComponentConfig(CommonVideoMixerComponentConfig):
    driver: Literal[VideoMixerDriver.FFMPEG]
    actions: List[VideoMixerActionConfig] = Field(default_factory=list)
