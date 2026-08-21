from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import VideoAnalyzerComponentConfig, VideoAnalyzerDriver
from mindor.dsl.schema.action import VideoAnalyzerActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext

class VideoAnalyzerService(AsyncService):
    def __init__(self, id: str, config: VideoAnalyzerComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: VideoAnalyzerComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: VideoAnalyzerActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: VideoAnalyzerActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_video_analyzer_service(driver: VideoAnalyzerDriver):
    def decorator(cls: Type[VideoAnalyzerService]) -> Type[VideoAnalyzerService]:
        VideoAnalyzerServiceRegistry[driver] = cls
        return cls
    return decorator

VideoAnalyzerServiceRegistry: Dict[VideoAnalyzerDriver, Type[VideoAnalyzerService]] = {}
