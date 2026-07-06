from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import VideoConverterActionConfig
from .common import CommonVideoConverterComponentConfig, VideoConverterDriver

class FfmpegVideoConverterComponentConfig(CommonVideoConverterComponentConfig):
    driver: Literal[VideoConverterDriver.FFMPEG]
    actions: List[VideoConverterActionConfig] = Field(default_factory=list)
