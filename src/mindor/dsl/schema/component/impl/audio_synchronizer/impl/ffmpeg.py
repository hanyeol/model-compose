from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import AudioSynchronizerActionConfig
from .common import CommonAudioSynchronizerComponentConfig, AudioSynchronizerDriver

class FFmpegAudioSynchronizerComponentConfig(CommonAudioSynchronizerComponentConfig):
    driver: Literal[AudioSynchronizerDriver.FFMPEG]
    actions: List[AudioSynchronizerActionConfig] = Field(default_factory=list)
