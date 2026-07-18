from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import ScreenCaptureActionConfig
from .common import CommonScreenCaptureComponentConfig, ScreenCaptureDriver

class FFmpegScreenCaptureComponentConfig(CommonScreenCaptureComponentConfig):
    driver: Literal[ScreenCaptureDriver.FFMPEG]
    actions: List[ScreenCaptureActionConfig] = Field(default_factory=list)
