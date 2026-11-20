from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import VideoFrameAnalyzerComponentConfig, VideoFrameAnalyzerDriverType
from mindor.dsl.schema.action import VideoFrameAnalyzerActionConfig
from mindor.core.foundation.async_service import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class VideoFrameAnalyzerDriver(ComponentDriver):
    config: VideoFrameAnalyzerComponentConfig

    async def run(self, action: VideoFrameAnalyzerActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: VideoFrameAnalyzerActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_video_frame_analyzer_driver(driver: VideoFrameAnalyzerDriverType):
    def decorator(cls: Type[VideoFrameAnalyzerDriver]) -> Type[VideoFrameAnalyzerDriver]:
        VideoFrameAnalyzerDriverRegistry[driver] = cls
        return cls
    return decorator

VideoFrameAnalyzerDriverRegistry: Dict[VideoFrameAnalyzerDriverType, Type[VideoFrameAnalyzerDriver]] = {}
