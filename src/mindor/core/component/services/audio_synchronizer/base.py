from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import AudioSynchronizerComponentConfig, AudioSynchronizerDriver
from mindor.dsl.schema.action import AudioSynchronizerActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext

class AudioSynchronizerService(AsyncService):
    def __init__(self, id: str, config: AudioSynchronizerComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: AudioSynchronizerComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: AudioSynchronizerActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: AudioSynchronizerActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_audio_synchronizer_service(driver: AudioSynchronizerDriver):
    def decorator(cls: Type[AudioSynchronizerService]) -> Type[AudioSynchronizerService]:
        AudioSynchronizerServiceRegistry[driver] = cls
        return cls
    return decorator

AudioSynchronizerServiceRegistry: Dict[AudioSynchronizerDriver, Type[AudioSynchronizerService]] = {}
