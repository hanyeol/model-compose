from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import AudioAnalyzerActionConfig
from .common import CommonAudioAnalyzerComponentConfig, AudioAnalyzerDriver

class FFmpegAudioAnalyzerComponentConfig(CommonAudioAnalyzerComponentConfig):
    driver: Literal[AudioAnalyzerDriver.FFMPEG]
    actions: List[AudioAnalyzerActionConfig] = Field(default_factory=list)
