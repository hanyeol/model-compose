from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import VideoMixerComponentConfig, VideoMixerDriver
from mindor.dsl.schema.action import VideoMixerActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext

class VideoMixerService(AsyncService):
    def __init__(self, id: str, config: VideoMixerComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: VideoMixerComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: VideoMixerActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: VideoMixerActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_video_mixer_service(driver: VideoMixerDriver):
    def decorator(cls: Type[VideoMixerService]) -> Type[VideoMixerService]:
        VideoMixerServiceRegistry[driver] = cls
        return cls
    return decorator

VideoMixerServiceRegistry: Dict[VideoMixerDriver, Type[VideoMixerService]] = {}
