from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class VideoMixerDriver(str, Enum):
    FFMPEG = "ffmpeg"

class CommonVideoMixerComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.VIDEO_MIXER]
    driver: VideoMixerDriver = Field(..., description="Backend implementation used for video mixing.")
