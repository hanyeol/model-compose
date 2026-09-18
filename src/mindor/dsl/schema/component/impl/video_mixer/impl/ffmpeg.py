from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import VideoMixerActionConfig
from .common import CommonVideoMixerComponentConfig, VideoMixerDriverType

class FFmpegVideoMixerComponentConfig(CommonVideoMixerComponentConfig):
    driver: Literal[VideoMixerDriverType.FFMPEG]
    actions: List[VideoMixerActionConfig] = Field(default_factory=list)
