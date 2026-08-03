from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import VideoClipperActionConfig
from .common import CommonVideoClipperComponentConfig, VideoClipperDriver

class FFmpegVideoClipperComponentConfig(CommonVideoClipperComponentConfig):
    driver: Literal[VideoClipperDriver.FFMPEG]
    actions: List[VideoClipperActionConfig] = Field(default_factory=list)
