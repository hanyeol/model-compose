from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import AudioMixerComponentConfig, AudioMixerDriver
from mindor.dsl.schema.action import AudioMixerActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext

class AudioMixerService(AsyncService):
    def __init__(self, id: str, config: AudioMixerComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: AudioMixerComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: AudioMixerActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: AudioMixerActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_audio_mixer_service(driver: AudioMixerDriver):
    def decorator(cls: Type[AudioMixerService]) -> Type[AudioMixerService]:
        AudioMixerServiceRegistry[driver] = cls
        return cls
    return decorator

AudioMixerServiceRegistry: Dict[AudioMixerDriver, Type[AudioMixerService]] = {}
