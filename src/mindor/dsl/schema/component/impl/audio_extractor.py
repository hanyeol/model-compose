from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import AudioExtractorActionConfig
from .common import CommonComponentConfig, ComponentType

class AudioExtractorDriver(str, Enum):
    FFMPEG = "ffmpeg"

class AudioExtractorComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.AUDIO_EXTRACTOR]
    driver: Union[AudioExtractorDriver, str] = Field(default=AudioExtractorDriver.FFMPEG, description="Audio extraction backend driver.")
    actions: List[AudioExtractorActionConfig] = Field(default_factory=list)
