from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import MusicScoreLoaderComponentConfig, MusicScoreLoaderDriverType
from mindor.dsl.schema.action import MusicScoreLoaderActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class MusicScoreLoaderDriver(ComponentDriver):
    def __init__(self, id: str, config: MusicScoreLoaderComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: MusicScoreLoaderComponentConfig = config

    async def run(self, action: MusicScoreLoaderActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: MusicScoreLoaderActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_music_score_loader_driver(driver: MusicScoreLoaderDriverType):
    def decorator(cls: Type[MusicScoreLoaderDriver]) -> Type[MusicScoreLoaderDriver]:
        MusicScoreLoaderDriverRegistry[driver] = cls
        return cls
    return decorator

MusicScoreLoaderDriverRegistry: Dict[MusicScoreLoaderDriverType, Type[MusicScoreLoaderDriver]] = {}
