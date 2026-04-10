from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import VideoConverterActionConfig
from .common import CommonComponentConfig, ComponentType

class VideoConverterDriver(str, Enum):
    FFMPEG = "ffmpeg"

class VideoConverterComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.VIDEO_CONVERTER]
    driver: Union[VideoConverterDriver, str] = Field(default=VideoConverterDriver.FFMPEG, description="Video conversion backend driver.")
    actions: List[VideoConverterActionConfig] = Field(default_factory=list)
