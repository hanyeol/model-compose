from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import VideoAnalyzerActionConfig
from .common import CommonVideoAnalyzerComponentConfig, VideoAnalyzerDriverType

class FFmpegVideoAnalyzerComponentConfig(CommonVideoAnalyzerComponentConfig):
    driver: Literal[VideoAnalyzerDriverType.FFMPEG]
    actions: List[VideoAnalyzerActionConfig] = Field(default_factory=list)
