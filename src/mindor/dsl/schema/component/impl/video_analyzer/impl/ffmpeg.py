from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import VideoAnalyzerActionConfig
from .common import CommonVideoAnalyzerComponentConfig, VideoAnalyzerDriver

class FFmpegVideoAnalyzerComponentConfig(CommonVideoAnalyzerComponentConfig):
    driver: Literal[VideoAnalyzerDriver.FFMPEG]
    actions: List[VideoAnalyzerActionConfig] = Field(default_factory=list)
