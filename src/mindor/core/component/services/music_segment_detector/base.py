from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import MusicSegmentDetectorComponentConfig, MusicSegmentDetectorDriverType
from mindor.dsl.schema.action import MusicSegmentDetectorActionConfig
from mindor.core.foundation.async_service import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class MusicSegmentDetectorDriver(ComponentDriver):
    config: MusicSegmentDetectorComponentConfig

    async def run(self, action: MusicSegmentDetectorActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: MusicSegmentDetectorActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_music_segment_detector_driver(driver: MusicSegmentDetectorDriverType):
    def decorator(cls: Type[MusicSegmentDetectorDriver]) -> Type[MusicSegmentDetectorDriver]:
        MusicSegmentDetectorDriverRegistry[driver] = cls
        return cls
    return decorator

MusicSegmentDetectorDriverRegistry: Dict[MusicSegmentDetectorDriverType, Type[MusicSegmentDetectorDriver]] = {}
