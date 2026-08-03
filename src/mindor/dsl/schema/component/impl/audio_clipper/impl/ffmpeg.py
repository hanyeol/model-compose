from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import AudioClipperActionConfig
from .common import CommonAudioClipperComponentConfig, AudioClipperDriver

class FFmpegAudioClipperComponentConfig(CommonAudioClipperComponentConfig):
    driver: Literal[AudioClipperDriver.FFMPEG]
    actions: List[AudioClipperActionConfig] = Field(default_factory=list)
