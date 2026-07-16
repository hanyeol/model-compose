from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import VideoEncoderComponentConfig, VideoEncoderDriver
from mindor.dsl.schema.action import VideoEncoderActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext
import asyncio

class VideoEncoderService(AsyncService):
    def __init__(self, id: str, config: VideoEncoderComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: VideoEncoderComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: VideoEncoderActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context, asyncio.get_running_loop())

    @abstractmethod
    async def _run(self, action: VideoEncoderActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        pass

def register_video_encoder_service(driver: VideoEncoderDriver):
    def decorator(cls: Type[VideoEncoderService]) -> Type[VideoEncoderService]:
        VideoEncoderServiceRegistry[driver] = cls
        return cls
    return decorator

VideoEncoderServiceRegistry: Dict[VideoEncoderDriver, Type[VideoEncoderService]] = {}
