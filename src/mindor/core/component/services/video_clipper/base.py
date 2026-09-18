from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import VideoClipperComponentConfig, VideoClipperDriverType
from mindor.dsl.schema.action import VideoClipperActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class VideoClipperDriver(ComponentDriver):
    def __init__(self, id: str, config: VideoClipperComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: VideoClipperComponentConfig = config

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: VideoClipperActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: VideoClipperActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_video_clipper_driver(driver: VideoClipperDriverType):
    def decorator(cls: Type[VideoClipperDriver]) -> Type[VideoClipperDriver]:
        VideoClipperDriverRegistry[driver] = cls
        return cls
    return decorator

VideoClipperDriverRegistry: Dict[VideoClipperDriverType, Type[VideoClipperDriver]] = {}
