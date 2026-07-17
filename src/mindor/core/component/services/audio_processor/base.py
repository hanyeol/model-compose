from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import AudioProcessorComponentConfig, AudioProcessorDriver
from mindor.dsl.schema.action import AudioProcessorActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext
import asyncio

class AudioProcessorService(AsyncService):
    def __init__(self, id: str, config: AudioProcessorComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: AudioProcessorComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: AudioProcessorActionConfig, context: ComponentActionContext) -> Any:
        return await self.run_in_thread(self._run, action, context, asyncio.get_running_loop())

    @abstractmethod
    async def _run(self, action: AudioProcessorActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        pass

def register_audio_processor_service(driver: AudioProcessorDriver):
    def decorator(cls: Type[AudioProcessorService]) -> Type[AudioProcessorService]:
        AudioProcessorServiceRegistry[driver] = cls
        return cls
    return decorator

AudioProcessorServiceRegistry: Dict[AudioProcessorDriver, Type[AudioProcessorService]] = {}
