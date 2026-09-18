from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import VideoAnalyzerComponentConfig, VideoAnalyzerDriverType
from mindor.dsl.schema.action import VideoAnalyzerActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class VideoAnalyzerDriver(ComponentDriver):
    def __init__(self, id: str, config: VideoAnalyzerComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: VideoAnalyzerComponentConfig = config

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: VideoAnalyzerActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: VideoAnalyzerActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_video_analyzer_driver(driver: VideoAnalyzerDriverType):
    def decorator(cls: Type[VideoAnalyzerDriver]) -> Type[VideoAnalyzerDriver]:
        VideoAnalyzerDriverRegistry[driver] = cls
        return cls
    return decorator

VideoAnalyzerDriverRegistry: Dict[VideoAnalyzerDriverType, Type[VideoAnalyzerDriver]] = {}
