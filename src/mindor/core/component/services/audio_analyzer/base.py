from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import AudioAnalyzerComponentConfig, AudioAnalyzerDriver
from mindor.dsl.schema.action import AudioAnalyzerActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext

class AudioAnalyzerService(AsyncService):
    def __init__(self, id: str, config: AudioAnalyzerComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: AudioAnalyzerComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: AudioAnalyzerActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: AudioAnalyzerActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_audio_analyzer_service(driver: AudioAnalyzerDriver):
    def decorator(cls: Type[AudioAnalyzerService]) -> Type[AudioAnalyzerService]:
        AudioAnalyzerServiceRegistry[driver] = cls
        return cls
    return decorator

AudioAnalyzerServiceRegistry: Dict[AudioAnalyzerDriver, Type[AudioAnalyzerService]] = {}
