from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import TranscriptCorrectorComponentConfig, TranscriptCorrectorDriverType
from mindor.dsl.schema.action import TranscriptCorrectorActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class TranscriptCorrectorDriver(ComponentDriver):
    def __init__(self, id: str, config: TranscriptCorrectorComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: TranscriptCorrectorComponentConfig = config

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: TranscriptCorrectorActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: TranscriptCorrectorActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_transcript_corrector_driver(driver: TranscriptCorrectorDriverType):
    def decorator(cls: Type[TranscriptCorrectorDriver]) -> Type[TranscriptCorrectorDriver]:
        TranscriptCorrectorDriverRegistry[driver] = cls
        return cls
    return decorator

TranscriptCorrectorDriverRegistry: Dict[TranscriptCorrectorDriverType, Type[TranscriptCorrectorDriver]] = {}
