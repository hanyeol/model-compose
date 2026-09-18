from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import FFmpegRtmpPublisherActionConfig
from .common import CommonRtmpPublisherComponentConfig, RtmpPublisherDriverType

class FFmpegRtmpPublisherComponentConfig(CommonRtmpPublisherComponentConfig):
    driver: Literal[RtmpPublisherDriverType.FFMPEG]
    actions: List[FFmpegRtmpPublisherActionConfig] = Field(default_factory=list)
