from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import VideoFrameExtractorActionConfig
from .common import CommonVideoFrameExtractorComponentConfig, VideoFrameExtractorDriverType

class FFmpegVideoFrameExtractorComponentConfig(CommonVideoFrameExtractorComponentConfig):
    driver: Literal[VideoFrameExtractorDriverType.FFMPEG]
    actions: List[VideoFrameExtractorActionConfig] = Field(default_factory=list)
