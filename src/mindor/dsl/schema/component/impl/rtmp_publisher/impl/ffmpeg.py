from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import FFmpegRtmpPublisherActionConfig
from .common import CommonRtmpPublisherComponentConfig, RtmpPublisherDriver

class FFmpegRtmpPublisherComponentConfig(CommonRtmpPublisherComponentConfig):
    driver: Literal[RtmpPublisherDriver.FFMPEG]
    actions: List[FFmpegRtmpPublisherActionConfig] = Field(default_factory=list)
