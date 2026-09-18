from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import AudioSilenceDetectorActionConfig
from .common import CommonAudioSilenceDetectorComponentConfig, AudioSilenceDetectorDriverType

class FFmpegAudioSilenceDetectorComponentConfig(CommonAudioSilenceDetectorComponentConfig):
    driver: Literal[AudioSilenceDetectorDriverType.FFMPEG]
    actions: List[AudioSilenceDetectorActionConfig] = Field(default_factory=list)
