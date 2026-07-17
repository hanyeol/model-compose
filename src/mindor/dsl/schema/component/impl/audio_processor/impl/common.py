from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class AudioProcessorDriver(str, Enum):
    NATIVE = "native"

class CommonAudioProcessorComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.AUDIO_PROCESSOR]
    driver: AudioProcessorDriver = Field(..., description="Audio processing backend driver.")
