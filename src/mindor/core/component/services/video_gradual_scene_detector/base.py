from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import VideoGradualSceneDetectorComponentConfig, VideoGradualSceneDetectorDriverType
from mindor.dsl.schema.action import VideoGradualSceneDetectorActionConfig
from mindor.core.foundation.async_service import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class VideoGradualSceneDetectorDriver(ComponentDriver):
    config: VideoGradualSceneDetectorComponentConfig

    async def run(self, action: VideoGradualSceneDetectorActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: VideoGradualSceneDetectorActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_video_gradual_scene_detector_driver(driver: VideoGradualSceneDetectorDriverType):
    def decorator(cls: Type[VideoGradualSceneDetectorDriver]) -> Type[VideoGradualSceneDetectorDriver]:
        VideoGradualSceneDetectorDriverRegistry[driver] = cls
        return cls
    return decorator

VideoGradualSceneDetectorDriverRegistry: Dict[VideoGradualSceneDetectorDriverType, Type[VideoGradualSceneDetectorDriver]] = {}
