from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import FFmpegVideoFrameExtractorActionConfig
from .common import CommonVideoFrameExtractorComponentConfig, VideoFrameExtractorDriverType

class FFmpegVideoFrameExtractorComponentConfig(CommonVideoFrameExtractorComponentConfig):
    driver: Literal[VideoFrameExtractorDriverType.FFMPEG]
    actions: List[FFmpegVideoFrameExtractorActionConfig] = Field(default_factory=list)
