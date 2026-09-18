from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import VideoEncoderComponentConfig, VideoEncoderDriverType
from mindor.dsl.schema.action import VideoEncoderActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class VideoEncoderDriver(ComponentDriver):
    def __init__(self, id: str, config: VideoEncoderComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: VideoEncoderComponentConfig = config

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: VideoEncoderActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: VideoEncoderActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_video_encoder_driver(driver: VideoEncoderDriverType):
    def decorator(cls: Type[VideoEncoderDriver]) -> Type[VideoEncoderDriver]:
        VideoEncoderDriverRegistry[driver] = cls
        return cls
    return decorator

VideoEncoderDriverRegistry: Dict[VideoEncoderDriverType, Type[VideoEncoderDriver]] = {}
