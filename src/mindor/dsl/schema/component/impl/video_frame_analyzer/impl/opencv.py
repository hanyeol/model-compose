from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import OpenCvVideoFrameAnalyzerActionConfig
from .common import CommonVideoFrameAnalyzerComponentConfig, VideoFrameAnalyzerDriverType

class OpenCvVideoFrameAnalyzerComponentConfig(CommonVideoFrameAnalyzerComponentConfig):
    driver: Literal[VideoFrameAnalyzerDriverType.OPENCV]
    actions: List[OpenCvVideoFrameAnalyzerActionConfig] = Field(default_factory=list)
