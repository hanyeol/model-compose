from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import VideoConverterComponentConfig, VideoConverterDriverType
from mindor.dsl.schema.action import VideoConverterActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class VideoConverterDriver(ComponentDriver):
    def __init__(self, id: str, config: VideoConverterComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: VideoConverterComponentConfig = config

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: VideoConverterActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: VideoConverterActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_video_converter_driver(driver: VideoConverterDriverType):
    def decorator(cls: Type[VideoConverterDriver]) -> Type[VideoConverterDriver]:
        VideoConverterDriverRegistry[driver] = cls
        return cls
    return decorator

VideoConverterDriverRegistry: Dict[VideoConverterDriverType, Type[VideoConverterDriver]] = {}
