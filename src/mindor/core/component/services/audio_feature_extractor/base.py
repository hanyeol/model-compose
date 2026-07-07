from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import AudioFeatureExtractorComponentConfig, AudioFeatureExtractorDriver
from mindor.dsl.schema.action import AudioFeatureExtractorActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext
import asyncio

class AudioFeatureExtractorService(AsyncService):
    def __init__(self, id: str, config: AudioFeatureExtractorComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: AudioFeatureExtractorComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: AudioFeatureExtractorActionConfig, context: ComponentActionContext) -> Any:
        loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
        return await self._run(action, context, loop)

    @abstractmethod
    async def _run(self, action: AudioFeatureExtractorActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        pass

def register_audio_feature_extractor_service(driver: AudioFeatureExtractorDriver):
    def decorator(cls: Type[AudioFeatureExtractorService]) -> Type[AudioFeatureExtractorService]:
        AudioFeatureExtractorServiceRegistry[driver] = cls
        return cls
    return decorator

AudioFeatureExtractorServiceRegistry: Dict[AudioFeatureExtractorDriver, Type[AudioFeatureExtractorService]] = {}
