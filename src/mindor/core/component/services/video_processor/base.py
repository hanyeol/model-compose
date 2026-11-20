from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import VideoProcessorComponentConfig, VideoProcessorDriverType
from mindor.dsl.schema.action import VideoProcessorActionConfig
from mindor.core.foundation.async_service import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class VideoProcessorDriver(ComponentDriver):
    config: VideoProcessorComponentConfig

    async def run(self, action: VideoProcessorActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: VideoProcessorActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_video_processor_driver(driver: VideoProcessorDriverType):
    def decorator(cls: Type[VideoProcessorDriver]) -> Type[VideoProcessorDriver]:
        VideoProcessorDriverRegistry[driver] = cls
        return cls
    return decorator

VideoProcessorDriverRegistry: Dict[VideoProcessorDriverType, Type[VideoProcessorDriver]] = {}
