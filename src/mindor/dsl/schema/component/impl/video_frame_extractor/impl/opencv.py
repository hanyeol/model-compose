from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import VideoFrameExtractorActionConfig
from .common import CommonVideoFrameExtractorComponentConfig, VideoFrameExtractorDriver

class OpencvVideoFrameExtractorComponentConfig(CommonVideoFrameExtractorComponentConfig):
    driver: Literal[VideoFrameExtractorDriver.OPENCV]
    actions: List[VideoFrameExtractorActionConfig] = Field(default_factory=list)
