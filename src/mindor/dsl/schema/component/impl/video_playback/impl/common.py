from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class VideoPlaybackDriver(str, Enum):
    FFPLAY = "ffplay"

class CommonVideoPlaybackComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.VIDEO_PLAYBACK]
    driver: VideoPlaybackDriver = Field(..., description="Backend implementation used for video playback.")
