from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import MusicSegmentDetectorComponentConfig, MusicSegmentDetectorDriver
from mindor.dsl.schema.action import MusicSegmentDetectorActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext

class MusicSegmentDetectorService(AsyncService):
    def __init__(self, id: str, config: MusicSegmentDetectorComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: MusicSegmentDetectorComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: MusicSegmentDetectorActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: MusicSegmentDetectorActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_music_segment_detector_service(driver: MusicSegmentDetectorDriver):
    def decorator(cls: Type[MusicSegmentDetectorService]) -> Type[MusicSegmentDetectorService]:
        MusicSegmentDetectorServiceRegistry[driver] = cls
        return cls
    return decorator

MusicSegmentDetectorServiceRegistry: Dict[MusicSegmentDetectorDriver, Type[MusicSegmentDetectorService]] = {}
