from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import AudioClipperComponentConfig, AudioClipperDriver
from mindor.dsl.schema.action import AudioClipperActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext

class AudioClipperService(AsyncService):
    def __init__(self, id: str, config: AudioClipperComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: AudioClipperComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: AudioClipperActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: AudioClipperActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_audio_clipper_service(driver: AudioClipperDriver):
    def decorator(cls: Type[AudioClipperService]) -> Type[AudioClipperService]:
        AudioClipperServiceRegistry[driver] = cls
        return cls
    return decorator

AudioClipperServiceRegistry: Dict[AudioClipperDriver, Type[AudioClipperService]] = {}
