from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import AudioClipperActionConfig
from .common import CommonAudioClipperComponentConfig, AudioClipperDriverType

class FFmpegAudioClipperComponentConfig(CommonAudioClipperComponentConfig):
    driver: Literal[AudioClipperDriverType.FFMPEG]
    actions: List[AudioClipperActionConfig] = Field(default_factory=list)
