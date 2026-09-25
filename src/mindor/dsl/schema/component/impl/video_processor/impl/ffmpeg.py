from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import FFmpegVideoProcessorActionConfig
from .common import CommonVideoProcessorComponentConfig, VideoProcessorDriverType

class FFmpegVideoProcessorComponentConfig(CommonVideoProcessorComponentConfig):
    driver: Literal[VideoProcessorDriverType.FFMPEG]
    actions: List[FFmpegVideoProcessorActionConfig] = Field(default_factory=list)
