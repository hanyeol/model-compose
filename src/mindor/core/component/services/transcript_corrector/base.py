from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import TranscriptCorrectorComponentConfig, TranscriptCorrectorDriverType
from mindor.dsl.schema.action import TranscriptCorrectorActionConfig
from mindor.core.foundation.async_service import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class TranscriptCorrectorDriver(ComponentDriver):
    config: TranscriptCorrectorComponentConfig

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
