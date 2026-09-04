from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import MusicAnalyzerComponentConfig, MusicAnalyzerDriver
from mindor.dsl.schema.action import MusicAnalyzerActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext

class MusicAnalyzerService(AsyncService):
    def __init__(self, id: str, config: MusicAnalyzerComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: MusicAnalyzerComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: MusicAnalyzerActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: MusicAnalyzerActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_music_analyzer_service(driver: MusicAnalyzerDriver):
    def decorator(cls: Type[MusicAnalyzerService]) -> Type[MusicAnalyzerService]:
        MusicAnalyzerServiceRegistry[driver] = cls
        return cls
    return decorator

MusicAnalyzerServiceRegistry: Dict[MusicAnalyzerDriver, Type[MusicAnalyzerService]] = {}
