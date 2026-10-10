from typing import Type, Optional, Dict, List, Any, Union, Tuple
from abc import abstractmethod
from mindor.dsl.schema.component import MusicPitchCorrectorComponentConfig, MusicPitchCorrectorDriverType
from mindor.dsl.schema.action import MusicPitchCorrectorActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class MusicPitchCorrectorDriver(ComponentDriver):
    def __init__(self, id: str, config: MusicPitchCorrectorComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: MusicPitchCorrectorComponentConfig = config

    async def run(self, action: MusicPitchCorrectorActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: MusicPitchCorrectorActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_music_pitch_corrector_driver(driver: MusicPitchCorrectorDriverType):
    def decorator(cls: Type[MusicPitchCorrectorDriver]) -> Type[MusicPitchCorrectorDriver]:
        MusicPitchCorrectorDriverRegistry[driver] = cls
        return cls
    return decorator

MusicPitchCorrectorDriverRegistry: Dict[MusicPitchCorrectorDriverType, Type[MusicPitchCorrectorDriver]] = {}
