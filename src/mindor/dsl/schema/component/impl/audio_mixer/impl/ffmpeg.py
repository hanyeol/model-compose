from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import AudioMixerActionConfig
from .common import CommonAudioMixerComponentConfig, AudioMixerDriver

class FFmpegAudioMixerComponentConfig(CommonAudioMixerComponentConfig):
    driver: Literal[AudioMixerDriver.FFMPEG]
    actions: List[AudioMixerActionConfig] = Field(default_factory=list)
