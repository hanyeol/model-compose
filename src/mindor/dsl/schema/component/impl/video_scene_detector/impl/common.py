from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class VideoSceneDetectorDriverType(str, Enum):
    PYSCENEDETECT = "pyscenedetect"
    FFMPEG        = "ffmpeg"

class CommonVideoSceneDetectorComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.VIDEO_SCENE_DETECTOR]
    driver: VideoSceneDetectorDriverType = Field(..., description="Backend implementation used to detect scene changes.")
