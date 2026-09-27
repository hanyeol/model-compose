from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import FFmpegAudioSynchronizerActionConfig
from .common import CommonAudioSynchronizerComponentConfig, AudioSynchronizerDriverType

class FFmpegAudioSynchronizerComponentConfig(CommonAudioSynchronizerComponentConfig):
    driver: Literal[AudioSynchronizerDriverType.FFMPEG]
    actions: List[FFmpegAudioSynchronizerActionConfig] = Field(default_factory=list)
