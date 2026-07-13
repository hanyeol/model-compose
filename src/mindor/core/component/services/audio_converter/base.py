from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import AudioConverterComponentConfig, AudioConverterDriver
from mindor.dsl.schema.action import AudioConverterActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext
import asyncio

class AudioConverterService(AsyncService):
    def __init__(self, id: str, config: AudioConverterComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: AudioConverterComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: AudioConverterActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context, asyncio.get_running_loop())

    @abstractmethod
    async def _run(self, action: AudioConverterActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        pass

def register_audio_converter_service(driver: AudioConverterDriver):
    def decorator(cls: Type[AudioConverterService]) -> Type[AudioConverterService]:
        AudioConverterServiceRegistry[driver] = cls
        return cls
    return decorator

AudioConverterServiceRegistry: Dict[AudioConverterDriver, Type[AudioConverterService]] = {}
