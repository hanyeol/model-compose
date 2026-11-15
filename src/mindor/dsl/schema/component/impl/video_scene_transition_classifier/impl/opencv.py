from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import OpenCvVideoSceneTransitionClassifierActionConfig
from .common import CommonVideoSceneTransitionClassifierComponentConfig, VideoSceneTransitionClassifierDriverType

class OpenCvVideoSceneTransitionClassifierComponentConfig(CommonVideoSceneTransitionClassifierComponentConfig):
    driver: Literal[VideoSceneTransitionClassifierDriverType.OPENCV]
    actions: List[OpenCvVideoSceneTransitionClassifierActionConfig] = Field(default_factory=list)
