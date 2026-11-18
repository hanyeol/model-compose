from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class VideoGradualSceneDetectorDriverType(str, Enum):
    OPENCV = "opencv"

class CommonVideoGradualSceneDetectorComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.VIDEO_GRADUAL_SCENE_DETECTOR]
    driver: VideoGradualSceneDetectorDriverType = Field(..., description="Backend implementation used to scan for gradual scene boundaries.")
