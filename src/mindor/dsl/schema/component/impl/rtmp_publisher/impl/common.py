from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class RtmpPublisherDriver(str, Enum):
    FFMPEG = "ffmpeg"

class CommonRtmpPublisherComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.RTMP_PUBLISHER]
    driver: RtmpPublisherDriver = Field(..., description="RTMP publisher backend driver.")
