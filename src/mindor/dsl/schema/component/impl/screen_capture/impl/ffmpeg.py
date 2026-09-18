from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import ScreenCaptureActionConfig
from .common import CommonScreenCaptureComponentConfig, ScreenCaptureDriverType

class FFmpegScreenCaptureComponentConfig(CommonScreenCaptureComponentConfig):
    driver: Literal[ScreenCaptureDriverType.FFMPEG]
    actions: List[ScreenCaptureActionConfig] = Field(default_factory=list)
