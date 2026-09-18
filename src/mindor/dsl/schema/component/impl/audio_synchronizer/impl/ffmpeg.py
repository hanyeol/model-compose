from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import AudioSynchronizerActionConfig
from .common import CommonAudioSynchronizerComponentConfig, AudioSynchronizerDriverType

class FFmpegAudioSynchronizerComponentConfig(CommonAudioSynchronizerComponentConfig):
    driver: Literal[AudioSynchronizerDriverType.FFMPEG]
    actions: List[AudioSynchronizerActionConfig] = Field(default_factory=list)
