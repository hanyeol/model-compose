from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import VideoEncoderActionConfig
from .common import CommonVideoEncoderComponentConfig, VideoEncoderDriverType

class FFmpegVideoEncoderComponentConfig(CommonVideoEncoderComponentConfig):
    driver: Literal[VideoEncoderDriverType.FFMPEG]
    actions: List[VideoEncoderActionConfig] = Field(default_factory=list)
