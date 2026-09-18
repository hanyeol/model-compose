from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import VideoConverterActionConfig
from .common import CommonVideoConverterComponentConfig, VideoConverterDriverType

class FFmpegVideoConverterComponentConfig(CommonVideoConverterComponentConfig):
    driver: Literal[VideoConverterDriverType.FFMPEG]
    actions: List[VideoConverterActionConfig] = Field(default_factory=list)
