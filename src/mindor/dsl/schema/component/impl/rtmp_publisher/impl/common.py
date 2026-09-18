from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class RtmpPublisherDriverType(str, Enum):
    FFMPEG = "ffmpeg"

class CommonRtmpPublisherComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.RTMP_PUBLISHER]
    driver: RtmpPublisherDriverType = Field(..., description="Backend implementation used to publish RTMP streams.")
