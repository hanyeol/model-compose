from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import VideoProcessorActionConfig
from .common import CommonVideoProcessorComponentConfig, VideoProcessorDriverType

class FFmpegVideoProcessorComponentConfig(CommonVideoProcessorComponentConfig):
    driver: Literal[VideoProcessorDriverType.FFMPEG]
    actions: List[VideoProcessorActionConfig] = Field(default_factory=list)
