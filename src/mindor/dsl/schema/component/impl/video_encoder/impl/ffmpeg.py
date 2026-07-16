from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import VideoEncoderActionConfig
from .common import CommonVideoEncoderComponentConfig, VideoEncoderDriver

class FFmpegVideoEncoderComponentConfig(CommonVideoEncoderComponentConfig):
    driver: Literal[VideoEncoderDriver.FFMPEG]
    actions: List[VideoEncoderActionConfig] = Field(default_factory=list)
