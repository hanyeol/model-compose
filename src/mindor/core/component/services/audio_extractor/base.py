from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.component import AudioExtractorComponentConfig, AudioExtractorDriver
from mindor.dsl.schema.action import AudioExtractorActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext
import asyncio

class AudioExtractorService(AsyncService):
    def __init__(self, id: str, config: AudioExtractorComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: AudioExtractorComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: AudioExtractorActionConfig, context: ComponentActionContext) -> Any:
        loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
        return await self._run(action, context, loop)

    @abstractmethod
    async def _run(self, action: AudioExtractorActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        pass

def register_audio_extractor_service(driver: AudioExtractorDriver):
    def decorator(cls: Type[AudioExtractorService]) -> Type[AudioExtractorService]:
        AudioExtractorServiceRegistry[driver] = cls
        return cls
    return decorator

AudioExtractorServiceRegistry: Dict[AudioExtractorDriver, Type[AudioExtractorService]] = {}
