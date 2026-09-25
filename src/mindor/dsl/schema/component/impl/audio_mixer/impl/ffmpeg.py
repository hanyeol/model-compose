from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import FFmpegAudioMixerActionConfig
from .common import CommonAudioMixerComponentConfig, AudioMixerDriverType

class FFmpegAudioMixerComponentConfig(CommonAudioMixerComponentConfig):
    driver: Literal[AudioMixerDriverType.FFMPEG]
    actions: List[FFmpegAudioMixerActionConfig] = Field(default_factory=list)
