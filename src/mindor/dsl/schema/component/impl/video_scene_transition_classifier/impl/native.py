from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import NativeVideoSceneTransitionClassifierActionConfig
from .common import CommonVideoSceneTransitionClassifierComponentConfig, VideoSceneTransitionClassifierDriverType

class NativeVideoSceneTransitionClassifierComponentConfig(CommonVideoSceneTransitionClassifierComponentConfig):
    driver: Literal[VideoSceneTransitionClassifierDriverType.NATIVE]
    actions: List[NativeVideoSceneTransitionClassifierActionConfig] = Field(default_factory=list)
