from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import NativeVideoFrameAnalyzerActionConfig
from .common import CommonVideoFrameAnalyzerComponentConfig, VideoFrameAnalyzerDriverType

class NativeVideoFrameAnalyzerComponentConfig(CommonVideoFrameAnalyzerComponentConfig):
    driver: Literal[VideoFrameAnalyzerDriverType.NATIVE]
    actions: List[NativeVideoFrameAnalyzerActionConfig] = Field(default_factory=list)
