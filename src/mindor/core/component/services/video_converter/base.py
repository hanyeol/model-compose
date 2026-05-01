from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import VideoConverterComponentConfig, VideoConverterDriver
from mindor.dsl.schema.action import VideoConverterActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext

class VideoConverterService(AsyncService):
    def __init__(self, id: str, config: VideoConverterComponentConfig, daemon: bool):
        super().__init__(daemon)
        self.id: str = id
        self.config: VideoConverterComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: VideoConverterActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: VideoConverterActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_video_converter_service(driver: VideoConverterDriver):
    def decorator(cls: Type[VideoConverterService]) -> Type[VideoConverterService]:
        VideoConverterServiceRegistry[driver] = cls
        return cls
    return decorator

VideoConverterServiceRegistry: Dict[VideoConverterDriver, Type[VideoConverterService]] = {}
