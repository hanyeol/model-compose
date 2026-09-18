from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import AudioProcessorComponentConfig, AudioProcessorDriverType
from mindor.dsl.schema.action import AudioProcessorActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class AudioProcessorDriver(ComponentDriver):
    def __init__(self, id: str, config: AudioProcessorComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: AudioProcessorComponentConfig = config

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: AudioProcessorActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: AudioProcessorActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_audio_processor_driver(driver: AudioProcessorDriverType):
    def decorator(cls: Type[AudioProcessorDriver]) -> Type[AudioProcessorDriver]:
        AudioProcessorDriverRegistry[driver] = cls
        return cls
    return decorator

AudioProcessorDriverRegistry: Dict[AudioProcessorDriverType, Type[AudioProcessorDriver]] = {}
