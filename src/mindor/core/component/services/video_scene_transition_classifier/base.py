from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import VideoSceneTransitionClassifierComponentConfig, VideoSceneTransitionClassifierDriverType
from mindor.dsl.schema.action import VideoSceneTransitionClassifierActionConfig
from mindor.core.foundation.async_service import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class VideoSceneTransitionClassifierDriver(ComponentDriver):
    def __init__(self, id: str, config: VideoSceneTransitionClassifierComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: VideoSceneTransitionClassifierComponentConfig = config

    async def run(self, action: VideoSceneTransitionClassifierActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: VideoSceneTransitionClassifierActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_video_scene_transition_classifier_driver(driver: VideoSceneTransitionClassifierDriverType):
    def decorator(cls: Type[VideoSceneTransitionClassifierDriver]) -> Type[VideoSceneTransitionClassifierDriver]:
        VideoSceneTransitionClassifierDriverRegistry[driver] = cls
        return cls
    return decorator

VideoSceneTransitionClassifierDriverRegistry: Dict[VideoSceneTransitionClassifierDriverType, Type[VideoSceneTransitionClassifierDriver]] = {}
