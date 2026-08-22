from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import VideoProcessorActionConfig
from .common import CommonVideoProcessorComponentConfig, VideoProcessorDriver

class FFmpegVideoProcessorComponentConfig(CommonVideoProcessorComponentConfig):
    driver: Literal[VideoProcessorDriver.FFMPEG]
    actions: List[VideoProcessorActionConfig] = Field(default_factory=list)
