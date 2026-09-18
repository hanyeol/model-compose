from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import AudioClipperComponentConfig, AudioClipperDriverType
from mindor.dsl.schema.action import AudioClipperActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class AudioClipperDriver(ComponentDriver):
    def __init__(self, id: str, config: AudioClipperComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: AudioClipperComponentConfig = config

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: AudioClipperActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: AudioClipperActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_audio_clipper_driver(driver: AudioClipperDriverType):
    def decorator(cls: Type[AudioClipperDriver]) -> Type[AudioClipperDriver]:
        AudioClipperDriverRegistry[driver] = cls
        return cls
    return decorator

AudioClipperDriverRegistry: Dict[AudioClipperDriverType, Type[AudioClipperDriver]] = {}
