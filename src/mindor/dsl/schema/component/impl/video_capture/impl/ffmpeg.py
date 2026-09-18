from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import VideoCaptureActionConfig
from .common import CommonVideoCaptureComponentConfig, VideoCaptureDriverType

class FFmpegVideoCaptureComponentConfig(CommonVideoCaptureComponentConfig):
    driver: Literal[VideoCaptureDriverType.FFMPEG]
    actions: List[VideoCaptureActionConfig] = Field(default_factory=list)
