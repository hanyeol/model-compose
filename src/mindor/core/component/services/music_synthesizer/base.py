from typing import Type, Optional, Dict, List, Any, Union, Tuple
from abc import abstractmethod
from mindor.dsl.schema.component import MusicSynthesizerComponentConfig, MusicSynthesizerDriverType
from mindor.dsl.schema.action import MusicSynthesizerActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class MusicSynthesizerDriver(ComponentDriver):
    def __init__(self, id: str, config: MusicSynthesizerComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: MusicSynthesizerComponentConfig = config

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return None

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
