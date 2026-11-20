from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import MusicAnalyzerComponentConfig, MusicAnalyzerDriverType
from mindor.dsl.schema.action import MusicAnalyzerActionConfig
from mindor.core.foundation.async_service import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class MusicAnalyzerDriver(ComponentDriver):
    config: MusicAnalyzerComponentConfig

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
