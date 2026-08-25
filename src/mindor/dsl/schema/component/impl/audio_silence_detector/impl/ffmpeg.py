from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import AudioSilenceDetectorActionConfig
from .common import CommonAudioSilenceDetectorComponentConfig, AudioSilenceDetectorDriver

class FFmpegAudioSilenceDetectorComponentConfig(CommonAudioSilenceDetectorComponentConfig):
    driver: Literal[AudioSilenceDetectorDriver.FFMPEG]
    actions: List[AudioSilenceDetectorActionConfig] = Field(default_factory=list)
