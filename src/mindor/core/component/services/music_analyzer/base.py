from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import MusicAnalyzerComponentConfig, MusicAnalyzerDriverType
from mindor.dsl.schema.action import MusicAnalyzerActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class MusicAnalyzerDriver(ComponentDriver):
    def __init__(self, id: str, config: MusicAnalyzerComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: MusicAnalyzerComponentConfig = config

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: MusicAnalyzerActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: MusicAnalyzerActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_music_analyzer_driver(driver: MusicAnalyzerDriverType):
    def decorator(cls: Type[MusicAnalyzerDriver]) -> Type[MusicAnalyzerDriver]:
        MusicAnalyzerDriverRegistry[driver] = cls
        return cls
    return decorator

MusicAnalyzerDriverRegistry: Dict[MusicAnalyzerDriverType, Type[MusicAnalyzerDriver]] = {}
