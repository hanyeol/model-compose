from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import VideoPlaybackComponentConfig, VideoPlaybackDriverType
from mindor.dsl.schema.action import VideoPlaybackActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class VideoPlaybackDriver(ComponentDriver):
    def __init__(self, id: str, config: VideoPlaybackComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: VideoPlaybackComponentConfig = config

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return None

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
