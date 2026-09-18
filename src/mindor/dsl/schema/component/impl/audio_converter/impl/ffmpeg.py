from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import AudioConverterActionConfig
from .common import CommonAudioConverterComponentConfig, AudioConverterDriverType

class FFmpegAudioConverterComponentConfig(CommonAudioConverterComponentConfig):
    driver: Literal[AudioConverterDriverType.FFMPEG]
    actions: List[AudioConverterActionConfig] = Field(default_factory=list)
