from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import VideoSceneDetectorActionConfig
from .common import CommonComponentConfig, ComponentType

class VideoSceneDetectorDriver(str, Enum):
    PYSCENEDETECT = "pyscenedetect"
    FFMPEG        = "ffmpeg"
    TRANSNETV2    = "transnetv2"

class VideoSceneDetectorComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.VIDEO_SCENE_DETECTOR]
    driver: Union[VideoSceneDetectorDriver, str] = Field(default=VideoSceneDetectorDriver.PYSCENEDETECT, description="Scene detection backend driver.")
    actions: List[VideoSceneDetectorActionConfig] = Field(default_factory=list)
