from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import VideoMixerComponentConfig, VideoMixerDriverType
from mindor.dsl.schema.action import VideoMixerActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class VideoMixerDriver(ComponentDriver):
    def __init__(self, id: str, config: VideoMixerComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: VideoMixerComponentConfig = config

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: VideoMixerActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: VideoMixerActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_video_mixer_driver(driver: VideoMixerDriverType):
    def decorator(cls: Type[VideoMixerDriver]) -> Type[VideoMixerDriver]:
        VideoMixerDriverRegistry[driver] = cls
        return cls
    return decorator

VideoMixerDriverRegistry: Dict[VideoMixerDriverType, Type[VideoMixerDriver]] = {}
