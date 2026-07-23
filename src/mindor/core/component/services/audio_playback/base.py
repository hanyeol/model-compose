from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import AudioPlaybackComponentConfig, AudioPlaybackDriver
from mindor.dsl.schema.action import AudioPlaybackActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext
import asyncio

class AudioPlaybackService(AsyncService):
    def __init__(self, id: str, config: AudioPlaybackComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: AudioPlaybackComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: AudioPlaybackActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context, asyncio.get_running_loop())

    @abstractmethod
    async def _run(self, action: AudioPlaybackActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        pass

def register_audio_playback_service(driver: AudioPlaybackDriver):
    def decorator(cls: Type[AudioPlaybackService]) -> Type[AudioPlaybackService]:
        AudioPlaybackServiceRegistry[driver] = cls
        return cls
    return decorator

AudioPlaybackServiceRegistry: Dict[AudioPlaybackDriver, Type[AudioPlaybackService]] = {}
