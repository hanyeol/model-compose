from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import FFmpegAudioPlaybackActionConfig
from .common import CommonAudioPlaybackComponentConfig, AudioPlaybackDriverType

class FFmpegAudioPlaybackComponentConfig(CommonAudioPlaybackComponentConfig):
    driver: Literal[AudioPlaybackDriverType.FFMPEG]
    actions: List[FFmpegAudioPlaybackActionConfig] = Field(default_factory=list)
