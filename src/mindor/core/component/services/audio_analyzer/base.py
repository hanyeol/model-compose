from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import AudioAnalyzerComponentConfig, AudioAnalyzerDriverType
from mindor.dsl.schema.action import AudioAnalyzerActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class AudioAnalyzerDriver(ComponentDriver):
    def __init__(self, id: str, config: AudioAnalyzerComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: AudioAnalyzerComponentConfig = config

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: AudioAnalyzerActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: AudioAnalyzerActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_audio_analyzer_driver(driver: AudioAnalyzerDriverType):
    def decorator(cls: Type[AudioAnalyzerDriver]) -> Type[AudioAnalyzerDriver]:
        AudioAnalyzerDriverRegistry[driver] = cls
        return cls
    return decorator

AudioAnalyzerDriverRegistry: Dict[AudioAnalyzerDriverType, Type[AudioAnalyzerDriver]] = {}
