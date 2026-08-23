from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import VideoPlaybackComponentConfig, VideoPlaybackDriver
from mindor.dsl.schema.action import VideoPlaybackActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext

class VideoPlaybackService(AsyncService):
    def __init__(self, id: str, config: VideoPlaybackComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: VideoPlaybackComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: VideoPlaybackActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: VideoPlaybackActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_video_playback_service(driver: VideoPlaybackDriver):
    def decorator(cls: Type[VideoPlaybackService]) -> Type[VideoPlaybackService]:
        VideoPlaybackServiceRegistry[driver] = cls
        return cls
    return decorator

VideoPlaybackServiceRegistry: Dict[VideoPlaybackDriver, Type[VideoPlaybackService]] = {}
