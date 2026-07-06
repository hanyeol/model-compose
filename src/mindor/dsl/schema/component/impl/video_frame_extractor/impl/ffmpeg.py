from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import VideoFrameExtractorActionConfig
from .common import CommonVideoFrameExtractorComponentConfig, VideoFrameExtractorDriver

class FfmpegVideoFrameExtractorComponentConfig(CommonVideoFrameExtractorComponentConfig):
    driver: Literal[VideoFrameExtractorDriver.FFMPEG]
    actions: List[VideoFrameExtractorActionConfig] = Field(default_factory=list)
