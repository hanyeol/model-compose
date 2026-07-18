from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class ScreenCaptureDriver(str, Enum):
    FFMPEG = "ffmpeg"

class CommonScreenCaptureComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.SCREEN_CAPTURE]
    driver: ScreenCaptureDriver = Field(..., description="Screen capture backend driver.")
