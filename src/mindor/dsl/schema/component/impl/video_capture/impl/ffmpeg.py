from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import VideoCaptureActionConfig
from .common import CommonVideoCaptureComponentConfig, VideoCaptureDriver

class FFmpegVideoCaptureComponentConfig(CommonVideoCaptureComponentConfig):
    driver: Literal[VideoCaptureDriver.FFMPEG]
    actions: List[VideoCaptureActionConfig] = Field(default_factory=list)
