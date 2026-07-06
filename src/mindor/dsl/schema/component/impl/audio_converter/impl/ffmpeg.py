from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import AudioConverterActionConfig
from .common import CommonAudioConverterComponentConfig, AudioConverterDriver

class FfmpegAudioConverterComponentConfig(CommonAudioConverterComponentConfig):
    driver: Literal[AudioConverterDriver.FFMPEG]
    actions: List[AudioConverterActionConfig] = Field(default_factory=list)
