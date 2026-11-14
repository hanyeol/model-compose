from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class VideoSceneTransitionClassifierDriverType(str, Enum):
    NATIVE = "native"

class CommonVideoSceneTransitionClassifierComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.VIDEO_SCENE_TRANSITION_CLASSIFIER]
    driver: VideoSceneTransitionClassifierDriverType = Field(..., description="Backend implementation used for scene transition classification.")
