from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import VideoPlaybackComponentConfig, VideoPlaybackDriverType
from mindor.dsl.schema.action import VideoPlaybackActionConfig
from mindor.core.foundation.async_service import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class VideoPlaybackDriver(ComponentDriver):
    config: VideoPlaybackComponentConfig

    async def run(self, action: VideoPlaybackActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: VideoPlaybackActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_video_playback_driver(driver: VideoPlaybackDriverType):
    def decorator(cls: Type[VideoPlaybackDriver]) -> Type[VideoPlaybackDriver]:
        VideoPlaybackDriverRegistry[driver] = cls
        return cls
    return decorator

VideoPlaybackDriverRegistry: Dict[VideoPlaybackDriverType, Type[VideoPlaybackDriver]] = {}
