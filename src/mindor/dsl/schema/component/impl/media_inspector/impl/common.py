from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class MediaInspectorDriver(str, Enum):
    FFMPEG   = "ffmpeg"
    EXIFTOOL = "exiftool"

class CommonMediaInspectorComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.MEDIA_INSPECTOR]
    driver: MediaInspectorDriver = Field(..., description="Media inspector backend driver.")
