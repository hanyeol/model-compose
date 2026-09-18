from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import AudioMixerComponentConfig, AudioMixerDriverType
from mindor.dsl.schema.action import AudioMixerActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class AudioMixerDriver(ComponentDriver):
    def __init__(self, id: str, config: AudioMixerComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: AudioMixerComponentConfig = config

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: AudioMixerActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: AudioMixerActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_audio_mixer_driver(driver: AudioMixerDriverType):
    def decorator(cls: Type[AudioMixerDriver]) -> Type[AudioMixerDriver]:
        AudioMixerDriverRegistry[driver] = cls
        return cls
    return decorator

AudioMixerDriverRegistry: Dict[AudioMixerDriverType, Type[AudioMixerDriver]] = {}
