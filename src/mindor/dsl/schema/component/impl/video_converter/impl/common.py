from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class VideoConverterDriver(str, Enum):
    FFMPEG = "ffmpeg"

class CommonVideoConverterComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.VIDEO_CONVERTER]
    driver: VideoConverterDriver = Field(..., description="Video conversion backend driver.")
