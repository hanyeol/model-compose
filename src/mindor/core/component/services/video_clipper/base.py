from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import VideoClipperComponentConfig, VideoClipperDriverType
from mindor.dsl.schema.action import VideoClipperActionConfig
from mindor.core.foundation.async_service import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class VideoClipperDriver(ComponentDriver):
    config: VideoClipperComponentConfig

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
