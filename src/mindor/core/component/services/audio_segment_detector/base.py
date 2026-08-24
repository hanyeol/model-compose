from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import AudioSegmentDetectorComponentConfig, AudioSegmentDetectorDriver
from mindor.dsl.schema.action import AudioSegmentDetectorActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext

class AudioSegmentDetectorService(AsyncService):
    def __init__(self, id: str, config: AudioSegmentDetectorComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: AudioSegmentDetectorComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: AudioSegmentDetectorActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: AudioSegmentDetectorActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_audio_segment_detector_service(driver: AudioSegmentDetectorDriver):
    def decorator(cls: Type[AudioSegmentDetectorService]) -> Type[AudioSegmentDetectorService]:
        AudioSegmentDetectorServiceRegistry[driver] = cls
        return cls
    return decorator

AudioSegmentDetectorServiceRegistry: Dict[AudioSegmentDetectorDriver, Type[AudioSegmentDetectorService]] = {}
