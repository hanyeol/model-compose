from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import MusicSynthesizerComponentConfig, MusicSynthesizerDriverType
from mindor.dsl.schema.action import MusicSynthesizerActionConfig
from mindor.core.foundation.async_service import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class MusicSynthesizerDriver(ComponentDriver):
    config: MusicSynthesizerComponentConfig

    async def run(self, action: MusicSynthesizerActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: MusicSynthesizerActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_music_synthesizer_driver(driver: MusicSynthesizerDriverType):
    def decorator(cls: Type[MusicSynthesizerDriver]) -> Type[MusicSynthesizerDriver]:
        MusicSynthesizerDriverRegistry[driver] = cls
        return cls
    return decorator

MusicSynthesizerDriverRegistry: Dict[MusicSynthesizerDriverType, Type[MusicSynthesizerDriver]] = {}
