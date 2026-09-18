from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class AudioProcessorDriverType(str, Enum):
    NATIVE = "native"

class CommonAudioProcessorComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.AUDIO_PROCESSOR]
    driver: AudioProcessorDriverType = Field(..., description="Backend implementation used for audio processing.")
