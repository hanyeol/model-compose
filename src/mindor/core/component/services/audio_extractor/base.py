from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import AudioExtractorComponentConfig, AudioExtractorDriverType
from mindor.dsl.schema.action import AudioExtractorActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class AudioExtractorDriver(ComponentDriver):
    def __init__(self, id: str, config: AudioExtractorComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: AudioExtractorComponentConfig = config

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: AudioExtractorActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: AudioExtractorActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_audio_extractor_driver(driver: AudioExtractorDriverType):
    def decorator(cls: Type[AudioExtractorDriver]) -> Type[AudioExtractorDriver]:
        AudioExtractorDriverRegistry[driver] = cls
        return cls
    return decorator

AudioExtractorDriverRegistry: Dict[AudioExtractorDriverType, Type[AudioExtractorDriver]] = {}
