from typing import Union, Literal, Optional, List
from enum import Enum
from pydantic import Field
from mindor.dsl.schema.action import AudioConverterActionConfig
from .common import CommonComponentConfig, ComponentType

class AudioConverterDriver(str, Enum):
    FFMPEG = "ffmpeg"

class AudioConverterComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.AUDIO_CONVERTER]
    driver: Union[AudioConverterDriver, str] = Field(default=AudioConverterDriver.FFMPEG, description="Audio conversion backend driver.")
    actions: List[AudioConverterActionConfig] = Field(default_factory=list)
