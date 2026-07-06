from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class VideoSceneDetectorDriver(str, Enum):
    PYSCENEDETECT = "pyscenedetect"
    FFMPEG        = "ffmpeg"
    TRANSNETV2    = "transnetv2"

class CommonVideoSceneDetectorComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.VIDEO_SCENE_DETECTOR]
    driver: VideoSceneDetectorDriver = Field(..., description="Scene detection backend driver.")
