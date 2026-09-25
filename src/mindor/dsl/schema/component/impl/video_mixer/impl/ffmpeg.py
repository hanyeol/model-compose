from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import FFmpegVideoMixerActionConfig
from .common import CommonVideoMixerComponentConfig, VideoMixerDriverType

class FFmpegVideoMixerComponentConfig(CommonVideoMixerComponentConfig):
    driver: Literal[VideoMixerDriverType.FFMPEG]
    actions: List[FFmpegVideoMixerActionConfig] = Field(default_factory=list)
