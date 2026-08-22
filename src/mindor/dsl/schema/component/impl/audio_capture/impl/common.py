from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class AudioCaptureDriver(str, Enum):
    FFMPEG = "ffmpeg"

class CommonAudioCaptureComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.AUDIO_CAPTURE]
    driver: AudioCaptureDriver = Field(..., description="Backend implementation used to capture audio.")
