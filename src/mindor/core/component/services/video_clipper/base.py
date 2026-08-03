from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import VideoClipperComponentConfig, VideoClipperDriver
from mindor.dsl.schema.action import VideoClipperActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext

class VideoClipperService(AsyncService):
    def __init__(self, id: str, config: VideoClipperComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: VideoClipperComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: VideoClipperActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: VideoClipperActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_video_clipper_service(driver: VideoClipperDriver):
    def decorator(cls: Type[VideoClipperService]) -> Type[VideoClipperService]:
        VideoClipperServiceRegistry[driver] = cls
        return cls
    return decorator

VideoClipperServiceRegistry: Dict[VideoClipperDriver, Type[VideoClipperService]] = {}
