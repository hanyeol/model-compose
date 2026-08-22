from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import VideoProcessorComponentConfig, VideoProcessorDriver
from mindor.dsl.schema.action import VideoProcessorActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext

class VideoProcessorService(AsyncService):
    def __init__(self, id: str, config: VideoProcessorComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: VideoProcessorComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: VideoProcessorActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: VideoProcessorActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_video_processor_service(driver: VideoProcessorDriver):
    def decorator(cls: Type[VideoProcessorService]) -> Type[VideoProcessorService]:
        VideoProcessorServiceRegistry[driver] = cls
        return cls
    return decorator

VideoProcessorServiceRegistry: Dict[VideoProcessorDriver, Type[VideoProcessorService]] = {}
