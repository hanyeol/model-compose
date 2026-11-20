from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import MusicScoreRendererComponentConfig, MusicScoreRendererDriverType
from mindor.dsl.schema.action import MusicScoreRendererActionConfig
from mindor.core.foundation.async_service import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class MusicScoreRendererDriver(ComponentDriver):
    config: MusicScoreRendererComponentConfig

    async def run(self, action: MusicScoreRendererActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: MusicScoreRendererActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_music_score_renderer_driver(driver: MusicScoreRendererDriverType):
    def decorator(cls: Type[MusicScoreRendererDriver]) -> Type[MusicScoreRendererDriver]:
        MusicScoreRendererDriverRegistry[driver] = cls
        return cls
    return decorator

MusicScoreRendererDriverRegistry: Dict[MusicScoreRendererDriverType, Type[MusicScoreRendererDriver]] = {}
