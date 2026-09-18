from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class ScreenCaptureDriverType(str, Enum):
    FFMPEG = "ffmpeg"

class CommonScreenCaptureComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.SCREEN_CAPTURE]
    driver: ScreenCaptureDriverType = Field(..., description="Backend implementation used to capture screen frames.")
