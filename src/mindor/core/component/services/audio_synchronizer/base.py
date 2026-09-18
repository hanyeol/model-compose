from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import AudioSynchronizerComponentConfig, AudioSynchronizerDriverType
from mindor.dsl.schema.action import AudioSynchronizerActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class AudioSynchronizerDriver(ComponentDriver):
    def __init__(self, id: str, config: AudioSynchronizerComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: AudioSynchronizerComponentConfig = config

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: AudioSynchronizerActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: AudioSynchronizerActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_audio_synchronizer_driver(driver: AudioSynchronizerDriverType):
    def decorator(cls: Type[AudioSynchronizerDriver]) -> Type[AudioSynchronizerDriver]:
        AudioSynchronizerDriverRegistry[driver] = cls
        return cls
    return decorator

AudioSynchronizerDriverRegistry: Dict[AudioSynchronizerDriverType, Type[AudioSynchronizerDriver]] = {}
