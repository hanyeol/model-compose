from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class VideoMixerDriverType(str, Enum):
    FFMPEG = "ffmpeg"

class CommonVideoMixerComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.VIDEO_MIXER]
    driver: VideoMixerDriverType = Field(..., description="Backend implementation used for video mixing.")
