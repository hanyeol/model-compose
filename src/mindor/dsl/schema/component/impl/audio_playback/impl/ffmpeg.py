from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import AudioPlaybackActionConfig
from .common import CommonAudioPlaybackComponentConfig, AudioPlaybackDriver

class FFmpegAudioPlaybackComponentConfig(CommonAudioPlaybackComponentConfig):
    driver: Literal[AudioPlaybackDriver.FFMPEG]
    actions: List[AudioPlaybackActionConfig] = Field(default_factory=list)
