from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import AudioPlaybackComponentConfig, AudioPlaybackDriverType
from mindor.dsl.schema.action import AudioPlaybackActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class AudioPlaybackDriver(ComponentDriver):
    def __init__(self, id: str, config: AudioPlaybackComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: AudioPlaybackComponentConfig = config

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: AudioPlaybackActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: AudioPlaybackActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_audio_playback_driver(driver: AudioPlaybackDriverType):
    def decorator(cls: Type[AudioPlaybackDriver]) -> Type[AudioPlaybackDriver]:
        AudioPlaybackDriverRegistry[driver] = cls
        return cls
    return decorator

AudioPlaybackDriverRegistry: Dict[AudioPlaybackDriverType, Type[AudioPlaybackDriver]] = {}
