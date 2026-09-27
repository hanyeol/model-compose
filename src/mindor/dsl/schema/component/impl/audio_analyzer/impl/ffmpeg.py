from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import FFmpegAudioAnalyzerActionConfig
from .common import CommonAudioAnalyzerComponentConfig, AudioAnalyzerDriverType

class FFmpegAudioAnalyzerComponentConfig(CommonAudioAnalyzerComponentConfig):
    driver: Literal[AudioAnalyzerDriverType.FFMPEG]
    actions: List[FFmpegAudioAnalyzerActionConfig] = Field(default_factory=list)
